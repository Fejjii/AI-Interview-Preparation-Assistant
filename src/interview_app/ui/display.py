from __future__ import annotations

"""
Reusable Streamlit output helpers (display functions).

Renders LLM responses, structured evaluations, guardrail summaries,
and debug metadata using card-based layouts with proper visual hierarchy.
"""

import json
from typing import Any

import streamlit as st

from interview_app.app.ui_settings import UISettings
from interview_app.cv.models import (
    CVAnalysisBundle,
    CVPracticeBundle,
    CVPracticeEvaluationBatch,
)
from interview_app.llm.model_settings import resolve_openai_model_id, sidebar_label_for_preset
from interview_app.security.guards import GuardrailResult
from interview_app.ui.presentation import show_technical_metadata
from interview_app.utils.interview_question_output import try_parse_questions_json
from interview_app.utils.types import EvaluationResult, LLMResponse
from interview_app.utils.usage_formatting import format_usage_summary


def _render_usage_caption(response: LLMResponse) -> None:
    """Compact usage line under LLM output (tokens, latency, optional estimate)."""
    if not show_technical_metadata():
        return
    summary = format_usage_summary(response)
    if summary:
        with st.expander("Usage", expanded=False):
            st.caption(summary)


def show_generated_questions_output(
    *,
    settings: UISettings,
    response: LLMResponse,
    title: str = "Interview output",
) -> None:
    """
    Structured presentation for generated questions: context, body, tips.
    Splits numbered lists into a highlighted first item when possible.
    """
    st.subheader(title)
    st.caption(f"{settings.role_category} · {settings.interview_focus} · {settings.persona}")

    text = (response.text or "").strip()
    parsed = try_parse_questions_json(text)

    st.markdown("---")
    if parsed:
        st.markdown("**Generated questions**")
        for i, item in enumerate(parsed, start=1):
            q = str(item.get("question", "")).strip()
            skill = str(item.get("skill_tested", "")).strip()
            diff = str(item.get("difficulty", "")).strip()
            why = str(item.get("why_it_matters", "")).strip()
            title = q[:90] + ("…" if len(q) > 90 else "")
            with st.expander(f"{i}. {title or 'Question'}", expanded=(i == 1)):
                st.markdown(q or "_Missing question text._")
                meta_parts = []
                if skill:
                    meta_parts.append(f"**Skill tested:** {skill}")
                if diff:
                    meta_parts.append(f"**Difficulty:** {diff}")
                if why:
                    meta_parts.append(f"**Why it matters:** {why}")
                if meta_parts:
                    st.caption(" · ".join(meta_parts))
    elif settings.prompt_strategy == "structured_output" and text:
        st.warning(
            "Structured output was selected, but the model response was not valid JSON. "
            "Showing raw text below."
        )
        st.code(text, language="json")
    else:
        main_q, follow_ups = _split_first_numbered_question(text)
        st.markdown("**Primary questions**")
        if main_q:
            st.success(main_q)
        else:
            st.markdown(text or "_No text returned._")

        if follow_ups:
            st.markdown("**Additional questions**")
            for i, line in enumerate(follow_ups, start=2):
                st.markdown(f"{i}. {line}")

    st.markdown("**What interviewers often look for**")
    st.info(
        f"Alignment with **{settings.interview_focus}**, clear examples, and depth "
        f"appropriate for **{settings.seniority}** in **{settings.interview_round}**."
    )

    st.markdown("**Tips**")
    st.warning(
        "Practice out loud. Time-box answers (2–3 minutes). Use the STAR method for behavioral prompts. "
        "Ask for a hint if you get stuck—real interviews allow clarification."
    )

    _render_usage_caption(response)

    if not show_technical_metadata():
        return

    with st.expander("Response metadata", expanded=False):
        st.code(
            json.dumps(
                {
                    "model": response.model,
                    "provider": response.provider,
                    "latency_ms": response.latency_ms,
                    "usage": (response.usage.model_dump() if response.usage else None),
                    "raw_response_id": response.raw_response_id,
                },
                indent=2,
            ),
            language="json",
        )


def _split_first_numbered_question(text: str) -> tuple[str, list[str]]:
    """Split numbered list: first line vs remaining lines (strip numbering)."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "", []

    def strip_num(line: str) -> str:
        for prefix in ("1.", "1)", "1 "):
            if line.startswith(prefix):
                return line[len(prefix) :].strip()
        if line and line[0].isdigit():
            for sep in (".", ")", " "):
                if sep in line[:4]:
                    idx = line.find(sep)
                    if idx >= 0 and idx < 3:
                        return line[idx + 1 :].strip()
        return line

    first = strip_num(lines[0])
    rest = [strip_num(line) for line in lines[1:]]
    return first, [r for r in rest if r]


def show_evaluation_dashboard(evaluation: EvaluationResult) -> None:
    """
    Evaluation feedback with metrics and structured sections (professional layout).
    """
    st.subheader("Evaluation results")

    strengths_list = evaluation.strengths or evaluation.criteria_met
    gaps_list = evaluation.improvements or evaluation.criteria_missing
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Overall score", f"{evaluation.score}/10")
    with m2:
        st.metric("Strengths noted", len(strengths_list))
    with m3:
        st.metric("Gaps flagged", len(gaps_list))

    st.markdown("---")
    follow = (
        [evaluation.next_follow_up_question]
        if evaluation.next_follow_up_question
        else evaluation.follow_ups
    )
    show_evaluation(
        score=evaluation.score,
        criteria_met=strengths_list,
        criteria_missing=gaps_list,
        critique=evaluation.critique,
        improved_answer=evaluation.improved_answer,
        follow_ups=follow,
        show_score_banner=False,
    )


def show_placeholder_result(*, title: str, body: str) -> None:
    """Render a success-style message for placeholder content."""
    st.success(title)
    st.markdown(body)


def show_error(*, title: str, body: str) -> None:
    """Render an error box with title and detail."""
    st.error(f"**{title}**")
    st.caption(body)


def show_llm_response(
    *,
    title: str,
    response: LLMResponse,
    settings: UISettings | None = None,
    structured: bool = False,
) -> None:
    """
    Render an `LLMResponse` with metadata in a collapsible section.

    If ``structured`` is True and ``settings`` is provided, uses the rich
    interview output layout (used for question generation).
    """
    if structured and settings is not None:
        show_generated_questions_output(settings=settings, response=response, title=title)
        return

    st.success(f"**{title}**")
    if response.text:
        st.markdown(response.text)
    else:
        st.warning("No text returned by the model.")

    _render_usage_caption(response)

    if not show_technical_metadata():
        return

    with st.expander("Response metadata", expanded=False):
        st.code(
            json.dumps(
                {
                    "model": response.model,
                    "provider": response.provider,
                    "latency_ms": response.latency_ms,
                    "usage": (response.usage.model_dump() if response.usage else None),
                    "raw_response_id": response.raw_response_id,
                },
                indent=2,
            ),
            language="json",
        )


def show_evaluation(
    *,
    score: int,
    criteria_met: list[str],
    criteria_missing: list[str],
    critique: str,
    improved_answer: str,
    follow_ups: list[str] | None = None,
    show_score_banner: bool = True,
) -> None:
    """Render structured evaluation with score, criteria, critique, and suggestions."""
    if show_score_banner:
        score_color = _score_color(score)
        st.markdown(
            f"""<div class="eval-card">
<div style="display:flex;align-items:baseline;gap:0.75rem;margin-bottom:0.75rem">
    <div>
        <div class="eval-score" style="color:{score_color}">{score}/10</div>
        <div class="eval-score-label">Overall Score</div>
    </div>
    <div style="flex:1">
        {_score_bar_html(score)}
    </div>
</div>
</div>""",
            unsafe_allow_html=True,
        )

    if criteria_met or criteria_missing:
        col_met, col_miss = st.columns(2)
        with col_met:
            if criteria_met:
                st.markdown("**Strengths**")
                for c in criteria_met:
                    st.markdown(f"- {c}")
        with col_miss:
            if criteria_missing:
                st.markdown("**Gaps to address**")
                for c in criteria_missing:
                    st.markdown(f"- {c}")

    if critique:
        st.markdown("---")
        st.markdown("**Critique**")
        st.info(critique)

    if improved_answer:
        st.markdown("**Stronger answer would include**")
        st.markdown(improved_answer)

    if follow_ups:
        st.markdown("**Suggested follow-ups**")
        for i, q in enumerate(follow_ups[:3], 1):
            st.markdown(f"{i}. {q}")


def show_evaluation_result(
    evaluation: EvaluationResult,
    *,
    llm_response: LLMResponse | None = None,
) -> None:
    """Render an EvaluationResult model with dashboard-style metrics."""
    show_evaluation_dashboard(evaluation)
    if llm_response is not None:
        _render_usage_caption(llm_response)


def show_cv_practice_bundle(*, bundle: CVPracticeBundle) -> None:
    """Practice mode: overview + questions only (no model answers)."""
    gen = bundle.practice_generation
    st.markdown("##### Candidate overview")
    st.markdown(gen.candidate_summary or "_No summary returned._")

    st.markdown("**Key skills**")
    if gen.key_skills:
        for s in gen.key_skills:
            st.markdown(f"- {s}")
    else:
        st.caption("—")

    st.markdown("**Themes from your CV**")
    if gen.themes_from_cv:
        st.info(", ".join(gen.themes_from_cv))
    else:
        st.caption("—")

    st.markdown("---")


def show_cv_practice_evaluation_batch(*, batch: CVPracticeEvaluationBatch) -> None:
    """Structured per-question feedback from practice evaluation."""
    st.markdown("##### Feedback on your answers")
    if not batch.evaluations:
        st.info("No evaluation items returned.")
        return

    for i, ev in enumerate(batch.evaluations, start=1):
        with st.container():
            st.markdown(f"**{i}.** {ev.question}")
            st.caption("Your answer")
            st.markdown(ev.user_answer or "_—_")
            if ev.score is not None:
                st.metric("Score", f"{ev.score}/10")
            if ev.feedback:
                st.markdown("**Feedback**")
                st.info(ev.feedback)
            if ev.strengths:
                st.markdown("**Strengths**")
                for s in ev.strengths:
                    st.markdown(f"- {s}")
            if ev.gaps:
                st.markdown("**Gaps / what is missing**")
                for g in ev.gaps:
                    st.markdown(f"- {g}")
            if ev.improved_answer_suggestion:
                st.markdown("**Improved answer suggestion**")
                st.success(ev.improved_answer_suggestion)
            if ev.follow_up_questions:
                st.markdown("**Follow-up questions**")
                for j, fq in enumerate(ev.follow_up_questions, start=1):
                    st.markdown(f"{j}. {fq}")
            st.markdown("---")


def show_cv_analysis_bundle(*, bundle: CVAnalysisBundle) -> None:
    """Render CV-grounded interview prep: summary, themes, and Q&A sections."""
    gen = bundle.generation
    st.markdown("##### Candidate overview")
    st.markdown(gen.candidate_summary or "_No summary returned._")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Key skills**")
        if gen.key_skills:
            for s in gen.key_skills:
                st.markdown(f"- {s}")
        else:
            st.caption("—")
    with c2:
        st.markdown("**Detected roles**")
        if gen.detected_roles:
            for r in gen.detected_roles:
                st.markdown(f"- {r}")
        else:
            st.caption("—")

    st.markdown("**Themes from your CV**")
    if gen.themes_from_cv:
        st.info(", ".join(gen.themes_from_cv))
    else:
        st.caption("—")

    st.markdown("---")
    st.markdown("##### Interview questions & answers")
    for i, item in enumerate(gen.interview_questions, start=1):
        with st.container():
            st.markdown(f"**{i}. ({item.category} · {item.difficulty})** {item.question}")
            if item.why_this_question:
                st.caption(f"Why this question: {item.why_this_question}")
            st.markdown("**Suggested answer**")
            st.success(item.suggested_answer or "_—_")
            if item.follow_up_questions:
                st.markdown("**Follow-up questions**")
                for j, fq in enumerate(item.follow_up_questions, start=1):
                    st.markdown(f"{j}. {fq}")
            st.markdown("---")


def show_guardrail_summary(*, guardrails: dict[str, GuardrailResult]) -> None:
    """Render guardrail output for flagged inputs only."""
    if not guardrails:
        return

    flagged = {k: v for k, v in guardrails.items() if not v.ok or v.flags}
    if not flagged:
        return

    with st.expander("Content review", expanded=False):
        for name, res in flagged.items():
            st.markdown(f"**{name.replace('_', ' ').title()}**")
            if res.flags:
                for flag in res.flags:
                    st.caption(f"• {flag}")
            else:
                st.caption("Review recommended.")


def show_prompt_debug(
    *,
    system_prompt: str,
    user_prompt: str,
    strategy_trace: dict[str, Any] | None = None,
) -> None:
    """Show the exact effective prompts sent to the model (opt-in sidebar debug)."""
    from interview_app.ui.presentation import allow_debug_prompts

    if not allow_debug_prompts():
        return
    with st.expander("Effective prompts (debug)", expanded=False):
        if strategy_trace:
            st.markdown("**Strategy build trace (debug)**")
            st.code(json.dumps(strategy_trace, indent=2), language="json")
        st.markdown("**Effective system prompt**")
        st.code(system_prompt, language="markdown")
        st.markdown("**Effective user prompt**")
        st.code(user_prompt, language="markdown")


def show_settings_debug(*, settings: UISettings, extra: dict[str, Any] | None = None) -> None:
    """Show a compact snapshot of current UI settings (opt-in debug)."""
    if not show_technical_metadata() and not settings.show_debug:
        return
    payload: dict[str, Any] = {
        "role_category": settings.role_category,
        "role_title": settings.role_title,
        "seniority": settings.seniority,
        "interview_round": settings.interview_round,
        "interview_focus": settings.interview_focus,
        "question_difficulty_mode": settings.question_difficulty_mode,
        "effective_question_difficulty": settings.effective_question_difficulty,
        "persona": settings.persona,
        "job_description_len": len(settings.job_description or ""),
        "prompt_strategy": settings.prompt_strategy,
        "model_preset": settings.model_preset,
        "model_label": sidebar_label_for_preset(settings.model_preset),
        "resolved_openai_model": resolve_openai_model_id(settings.model_preset),
        "temperature": settings.temperature,
        "top_p": settings.top_p,
        "max_tokens": settings.max_tokens,
    }
    if extra:
        payload["extra"] = extra

    with st.expander("Settings snapshot (debug)", expanded=False):
        st.code(json.dumps(payload, indent=2), language="json")


def _score_color(score: int) -> str:
    """Return a color for the evaluation score."""
    if score >= 8:
        return "var(--success)"
    if score >= 5:
        return "var(--warning)"
    return "var(--error)"


def _score_bar_html(score: int) -> str:
    """Return an HTML progress bar for the score."""
    pct = min(score * 10, 100)
    color = _score_color(score)
    return (
        f'<div style="width:100%;height:8px;background:var(--bg-tertiary);border-radius:4px;overflow:hidden;margin-top:0.5rem">'
        f'<div style="width:{pct}%;height:100%;background:{color};border-radius:4px;transition:width 0.6s ease"></div>'
        f"</div>"
    )
