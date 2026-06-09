"""Session-level interview context for mock interviews (accumulated candidate signals).

Stores merged ``InterviewTopicsDict`` in Streamlit/session dicts. Used when generating
the next question so the model drills into the candidate's stated tools and projects
instead of generic behavioral prompts.
"""

from __future__ import annotations

import re
from collections.abc import MutableMapping
from typing import Any, TypedDict

from interview_app.services.context_extractor import (
    InterviewTopicsDict,
    empty_interview_topics,
    extract_interview_topics,
    flatten_interview_topics,
    interview_topics_non_empty,
)
from interview_app.utils.types import ChatMessage

KEY_SESSION_INTERVIEW_CONTEXT = "ia_session_interview_context"
KEY_ACTIVE_INTERVIEW_QUESTION = "ia_mock_active_question"

# Caps keep prompts bounded; oldest entries naturally age out per bucket (merge truncates).
_MAX_PER_BUCKET = 32


class ActiveInterviewQuestionDict(TypedDict, total=False):
    """Grounding metadata for the question currently awaiting an answer."""

    question_text: str
    question_type: str
    based_on_topics: list[str]
    based_on_project: str
    expected_focus: list[str]


def init_session_interview_context(session_state: MutableMapping[str, Any]) -> None:
    if KEY_SESSION_INTERVIEW_CONTEXT not in session_state:
        session_state[KEY_SESSION_INTERVIEW_CONTEXT] = empty_interview_topics()


def flatten_session_context_for_evaluator(
    session_state: MutableMapping[str, Any] | None,
) -> list[str]:
    """Flatten stored interview context into tag-like strings for answer evaluation."""
    return flatten_interview_topics(get_session_interview_context(session_state), max_items=40)


def rebuild_session_interview_context_from_transcript(
    session_state: MutableMapping[str, Any] | None,
    messages: list[ChatMessage],
) -> None:
    """Restore accumulated context after loading a saved session (best-effort)."""
    if session_state is None:
        return
    clear_session_interview_context(session_state)
    for m in messages:
        if m.role == "user" and (m.content or "").strip():
            merge_message_into_session_context(session_state, m.content)


def clear_session_interview_context(session_state: MutableMapping[str, Any] | None) -> None:
    if session_state is None:
        return
    session_state[KEY_SESSION_INTERVIEW_CONTEXT] = empty_interview_topics()


def clear_active_interview_question(session_state: MutableMapping[str, Any] | None) -> None:
    if session_state is None:
        return
    session_state[KEY_ACTIVE_INTERVIEW_QUESTION] = None


def get_active_interview_question(
    session_state: MutableMapping[str, Any] | None,
) -> ActiveInterviewQuestionDict | None:
    if not session_state:
        return None
    raw = session_state.get(KEY_ACTIVE_INTERVIEW_QUESTION)
    if not isinstance(raw, dict):
        return None
    return raw  # type: ignore[return-value]


def set_active_interview_question(
    session_state: MutableMapping[str, Any] | None,
    *,
    question_text: str,
    question_type: str = "standard",
    based_on_topics: list[str] | None = None,
    based_on_project: str = "",
    expected_focus: list[str] | None = None,
) -> None:
    if session_state is None:
        return
    payload: ActiveInterviewQuestionDict = {
        "question_text": question_text,
        "question_type": question_type,
        "based_on_topics": list(based_on_topics or []),
        "based_on_project": (based_on_project or "").strip(),
        "expected_focus": list(expected_focus or []),
    }
    session_state[KEY_ACTIVE_INTERVIEW_QUESTION] = payload


def get_session_interview_context(
    session_state: MutableMapping[str, Any] | None,
) -> InterviewTopicsDict:
    if not session_state:
        return empty_interview_topics()
    raw = session_state.get(KEY_SESSION_INTERVIEW_CONTEXT)
    if not isinstance(raw, dict):
        return empty_interview_topics()
    out = empty_interview_topics()
    for k in out:
        v = raw.get(k)
        if k == "last_project_summary":
            if v is None:
                out[k] = ""
            else:
                out[k] = str(v).strip()[:4000]
        elif isinstance(v, list):
            out[k] = [str(x).strip() for x in v if str(x).strip()][:_MAX_PER_BUCKET]
        else:
            out[k] = empty_interview_topics()[k]  # type: ignore[index]
    return out


def merge_message_into_session_context(
    session_state: MutableMapping[str, Any] | None,
    message: str,
) -> InterviewTopicsDict:
    """Parse ``message`` and union into stored context; returns the updated snapshot."""
    if session_state is None:
        return empty_interview_topics()
    init_session_interview_context(session_state)
    incoming = extract_interview_topics(message, max_per_bucket=_MAX_PER_BUCKET)
    current = get_session_interview_context(session_state)
    merged: InterviewTopicsDict = empty_interview_topics()
    skip_union = frozenset({"recent_topics", "last_project_summary"})
    for key in merged:
        if key in skip_union:
            continue
        seen: set[str] = set()
        combined: list[str] = []
        for item in list(current[key]) + list(incoming[key]):  # type: ignore[arg-type]
            kl = item.strip().lower()
            if not kl or kl in seen:
                continue
            seen.add(kl)
            combined.append(item.strip())
            if len(combined) >= _MAX_PER_BUCKET:
                break
        merged[key] = combined  # type: ignore[index]
    merged["recent_topics"] = flatten_interview_topics(merged, max_items=24)
    prev_summary = (current.get("last_project_summary") or "").strip()
    if interview_topics_non_empty(incoming):
        new_s = (incoming.get("last_project_summary") or "").strip()
        merged["last_project_summary"] = new_s or prev_summary
    else:
        merged["last_project_summary"] = prev_summary
    session_state[KEY_SESSION_INTERVIEW_CONTEXT] = merged
    return merged


def context_summary_lines(ctx: InterviewTopicsDict) -> list[str]:
    """Human-readable lines for prompts (no markdown headers)."""
    lines: list[str] = []
    if ctx["tools"]:
        lines.append("Tools: " + ", ".join(ctx["tools"][:15]))
    if ctx["technologies"]:
        lines.append("Technologies: " + ", ".join(ctx["technologies"][:12]))
    if ctx["concepts"]:
        lines.append("Concepts: " + ", ".join(ctx["concepts"][:12]))
    if ctx["projects"]:
        lines.append("Projects / themes: " + ", ".join(ctx["projects"][:12]))
    if ctx["achievements"]:
        lines.append("Achievements / outcomes: " + ", ".join(ctx["achievements"][:10]))
    if ctx.get("domains"):
        lines.append("Domains: " + ", ".join(ctx["domains"][:10]))
    summary = (ctx.get("last_project_summary") or "").strip()
    if summary:
        lines.append("Latest project narrative (short): " + summary[:400])
    return lines


def format_context_for_question_prompt(ctx: InterviewTopicsDict) -> str:
    """Block appended to the question-generation user prompt when context applies."""
    if not interview_topics_non_empty(ctx):
        return ""
    lines = context_summary_lines(ctx)
    body = "\n".join(lines)
    return (
        "The candidate previously mentioned the following in this mock interview conversation:\n"
        f"{body}\n\n"
        "You are a technical interviewer. Generate the next question as a **deep technical follow-up** "
        "grounded in those specifics. Prefer angles such as: architecture, trade-offs, failure modes, "
        "debugging an incident, performance optimization, scaling, data quality, testing strategy, "
        "monitoring/observability, pipeline orchestration, and cost optimization — **not** a generic "
        "unrelated behavioral question unless there is no technical content above.\n"
        "Ask exactly one clear interview question."
    )


def user_requests_context_based_question(message: str) -> bool:
    """True when the user explicitly wants a follow-up tied to their prior story."""
    text_norm = re.sub(r"\s+", " ", (message or "").strip().lower())
    return _user_requests_context_question(text_norm)


def _user_requests_context_question(text_norm: str) -> bool:
    phrases = (
        "related to that",
        "related to this",
        "about that project",
        "about this project",
        "question related",
        "ask me a question related",
        "ask a question related",
        "ask me something about",
        "about what i said",
        "based on what i said",
        "based on my experience",
        "about my experience",
        "dig deeper",
        "drill into",
        "follow up on that",
        "follow-up on that",
        "something technical about",
    )
    return any(p in text_norm for p in phrases)


def _message_suggests_experience(text_norm: str) -> bool:
    markers = (
        "i built",
        "i implemented",
        "i designed",
        "i migrated",
        "we migrated",
        "we built",
        "in my last",
        "in my previous",
        "my team",
        "legacy",
        "production",
    )
    return any(m in text_norm for m in markers)


def should_use_context(
    user_message: str,
    session_state: MutableMapping[str, Any] | None,
) -> bool:
    """
    Whether mock-interview **question generation** should inject candidate context instructions.

    True when stored context is non-empty, the user explicitly asks for a related question,
    or the message looks like experience-sharing (already merged into context for this turn).
    """
    ctx = get_session_interview_context(session_state)
    text_norm = re.sub(r"\s+", " ", (user_message or "").strip().lower())

    if interview_topics_non_empty(ctx):
        return True
    if _user_requests_context_question(text_norm):
        return True
    if _message_suggests_experience(text_norm):
        return True
    return False


_COMPETENCY_ROTATION: tuple[str, ...] = (
    "architecture",
    "reliability",
    "evaluation",
    "guardrails",
    "deployment",
    "stakeholder communication",
    "tradeoffs",
)


def build_different_question_suffix(
    *,
    recent_questions: list[str],
    skipped_question: str | None,
    interview_focus: str,
    interview_round: str,
    seniority: str,
) -> str:
    """
    Negative context for skip / next-question generation: avoid repeating recent items.

    Appended to the question-generation user prompt (mock interview only).
    """
    avoid: list[str] = []
    seen: set[str] = set()
    for q in list(recent_questions) + ([skipped_question] if skipped_question else []):
        t = (q or "").strip()
        if not t:
            continue
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        avoid.append(t)
    if not avoid:
        return ""
    numbered = "\n".join(f"{i + 1}. {item}" for i, item in enumerate(avoid[-8:]))
    rotate_idx = len(avoid) % len(_COMPETENCY_ROTATION)
    next_angle = _COMPETENCY_ROTATION[rotate_idx]
    return (
        "The candidate skipped or asked for a **different** next question.\n"
        "Do **NOT** evaluate the skipped question.\n"
        "Recently asked questions (do NOT repeat wording, scenario, or competency):\n"
        f"{numbered}\n\n"
        f"Generate **one** clearly different question for a **{seniority}** candidate in "
        f"**{interview_round}** with focus **{interview_focus}**.\n"
        f"Prefer a fresh angle such as **{next_angle}**, and rotate away from the competencies "
        "already covered above. Keep the question realistic for the role and round."
    )


def build_question_generation_context_suffix(
    user_message: str,
    session_state: MutableMapping[str, Any] | None,
) -> str:
    """
    Extra user-prompt text for ``generate_questions`` during mock interview.

    When structured context exists, steers the model toward technical follow-ups.
    When the user explicitly asks for a related question but context is empty,
    asks for a technical deep-dive invite instead of a random behavioral item.
    """
    ctx = get_session_interview_context(session_state)
    text_norm = re.sub(r"\s+", " ", (user_message or "").strip().lower())
    if interview_topics_non_empty(ctx):
        return format_context_for_question_prompt(ctx)
    if _user_requests_context_question(text_norm):
        return (
            "The candidate asked for the **next question to relate to their recent project or prior answer**, "
            "but no structured tool/project list was captured yet.\n"
            "Ask **one** technical question that invites them to go deep on a concrete system they worked on "
            "(architecture, metrics, failures, testing, cost) - not a generic behavioral question."
        )
    return ""


def expected_focus_hints(ctx: InterviewTopicsDict, interview_focus: str) -> list[str]:
    """Short labels for ``active_interview_question.expected_focus`` (evaluation + follow-ups)."""
    out: list[str] = []
    focus = (interview_focus or "").strip()
    if focus:
        out.append(focus)
    if ctx.get("achievements"):
        out.append("Validation / quantified outcomes")
    if ctx.get("concepts"):
        out.append("Technical modeling / edge cases")
    for p in ctx.get("projects") or []:
        if "migration" in (p or "").lower():
            out.append("Migration / consistency / cutover")
            break
    if ctx.get("tools") or ctx.get("technologies"):
        out.append("Tooling and production trade-offs")
    return _unique_trimmed_list(out, cap=8)


def build_evaluation_active_question_hints(session_state: MutableMapping[str, Any] | None) -> str:
    """Extra evaluator instructions when the pending question was context-grounded."""
    active = get_active_interview_question(session_state)
    if not active:
        return ""
    lines: list[str] = []
    qtype = (active.get("question_type") or "").strip()
    if qtype in ("contextual_follow_up", "evaluator_follow_up"):
        lines.append(
            "Grading context: **contextual follow-up** tied to the candidate’s project story. "
            "Keep critique and the next follow-up anchored to that story (architecture, data quality, "
            "migration, performance validation) — avoid unrelated generic topics."
        )
    if active.get("based_on_project"):
        lines.append(f"Project anchor: {active['based_on_project'][:520]}")
    if active.get("based_on_topics"):
        lines.append("Topic tags: " + ", ".join(active["based_on_topics"][:18]))
    if active.get("expected_focus"):
        lines.append("Emphasis: " + "; ".join(active["expected_focus"][:8]))
    return "\n".join(lines).strip()


def _unique_trimmed_list(items: list[str], *, cap: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        t = x.strip()
        k = t.lower()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(t)
        if len(out) >= cap:
            break
    return out
