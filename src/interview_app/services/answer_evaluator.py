from __future__ import annotations

"""
Service: evaluate a candidate answer.

This module powers the "Answer feedback" tab and the chat flow.
Returns structured EvaluationResult (score, criteria, critique, improved snippet, follow-ups).
"""

import re
from dataclasses import dataclass
from typing import Any

from interview_app.app.interview_form_config import truncate_job_description, validate_role_title
from interview_app.llm.model_settings import resolve_openai_model_id
from interview_app.llm.openai_client import LLMClient
from interview_app.prompts.personas import get_persona_evaluation_rubric, get_persona_prompt
from interview_app.prompts.prompt_strategies import evaluation_coaching_directive
from interview_app.security.guards import GuardrailResult, protect_system_prompt
from interview_app.security.pipeline import run_input_pipeline, run_output_pipeline
from interview_app.utils.errors import safe_user_message
from interview_app.utils.language import language_instruction
from interview_app.utils.types import EvaluationResult, LLMResponse

_SERVICE_NAME = "answer_evaluator"


@dataclass(frozen=True)
class EvaluateAnswerResult:
    """Return type for `evaluate_answer` (easy to consume from Streamlit)."""

    ok: bool
    response: LLMResponse | None
    error: str | None
    guardrails: dict[str, GuardrailResult]
    system_prompt: str | None
    user_prompt: str | None
    evaluation: EvaluationResult | None = None


def evaluate_answer(
    *,
    role_category: str,
    role_title: str,
    seniority: str,
    interview_round: str,
    interview_focus: str,
    effective_difficulty: str,
    job_description: str = "",
    question: str,
    answer: str,
    model: str,
    temperature: float,
    max_tokens: int,
    top_p: float | None = None,
    response_language: str = "en",
    persona: str = "Hiring Manager",
    prompt_strategy: str | None = None,
    candidate_topics: list[str] | None = None,
    evaluation_context_hints: str = "",
    session_state: dict[str, Any] | None = None,
    skip_session_rate_limit: bool = False,
    openai_api_key: str | None = None,
) -> EvaluateAnswerResult:
    """
    Evaluate a user's answer to an interview question.
    Returns structured EvaluationResult when parsing succeeds.

    When ``skip_session_rate_limit`` is True, the session rate-limit step is skipped for
    pipeline fields inside this service (e.g. chat already consumed one unit for the turn).
    """

    guards: dict[str, GuardrailResult] = {}

    ok_title, role_trimmed = validate_role_title(role_title)
    if not ok_title:
        return EvaluateAnswerResult(
            ok=False,
            response=None,
            error="Please enter a role title in the sidebar.",
            guardrails=guards,
            system_prompt=None,
            user_prompt=None,
            evaluation=None,
        )

    role_pipe = run_input_pipeline(
        role_trimmed,
        field_name="role_title",
        max_chars=200,
        session_state=None,
        check_rate=False,
        service=_SERVICE_NAME,
    )
    if role_pipe.guardrail:
        guards["role_title"] = role_pipe.guardrail
    if not role_pipe.ok:
        return EvaluateAnswerResult(
            ok=False,
            response=None,
            error=role_pipe.error or "Invalid role title.",
            guardrails=guards,
            system_prompt=None,
            user_prompt=None,
            evaluation=None,
        )

    # --- Input pipeline ---
    q_pipe = run_input_pipeline(
        question or "",
        field_name="question",
        max_chars=4000,
        session_state=session_state,
        check_rate=not skip_session_rate_limit,
        service=_SERVICE_NAME,
    )
    if q_pipe.guardrail:
        guards["question"] = q_pipe.guardrail
    if not q_pipe.ok:
        return EvaluateAnswerResult(
            ok=False,
            response=None,
            error=q_pipe.error or "Question rejected by guardrails.",
            guardrails=guards,
            system_prompt=None,
            user_prompt=None,
            evaluation=None,
        )

    a_pipe = run_input_pipeline(
        answer or "",
        field_name="answer",
        max_chars=8000,
        session_state=None,
        check_rate=False,
        service=_SERVICE_NAME,
    )
    if a_pipe.guardrail:
        guards["answer"] = a_pipe.guardrail
    if not a_pipe.ok:
        return EvaluateAnswerResult(
            ok=False,
            response=None,
            error=a_pipe.error or "Answer rejected by guardrails.",
            guardrails=guards,
            system_prompt=None,
            user_prompt=None,
            evaluation=None,
        )

    system_prompt = protect_system_prompt(
        _evaluator_system_prompt(
            response_language=response_language,
            persona=persona,
            prompt_strategy=prompt_strategy,
        )
    )
    topics = [str(x).strip() for x in (candidate_topics or []) if str(x).strip()]
    jd_text = truncate_job_description(job_description)
    jd_pipe = run_input_pipeline(
        jd_text,
        field_name="job_description",
        max_chars=8000,
        session_state=None,
        check_rate=False,
        service=_SERVICE_NAME,
    )
    if jd_pipe.guardrail:
        guards["job_description"] = jd_pipe.guardrail
    if jd_text and not jd_pipe.ok:
        return EvaluateAnswerResult(
            ok=False,
            response=None,
            error=jd_pipe.error or "Job description rejected by guardrails.",
            guardrails=guards,
            system_prompt=None,
            user_prompt=None,
            evaluation=None,
        )

    user_prompt = _evaluator_user_prompt(
        role_category=role_category,
        role_title=role_pipe.cleaned_text,
        seniority=seniority,
        interview_round=interview_round,
        interview_focus=interview_focus,
        effective_difficulty=effective_difficulty,
        job_description=jd_pipe.cleaned_text if jd_text else "",
        question=q_pipe.cleaned_text,
        answer=a_pipe.cleaned_text,
        candidate_topics=topics,
        evaluation_context_hints=(evaluation_context_hints or "").strip(),
    )

    try:
        client = LLMClient(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            api_key=openai_api_key,
        )
        resp = client.generate_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            top_p=top_p,
            temperature=temperature,
            max_tokens=max_tokens,
            model=resolve_openai_model_id(model),
            llm_route=_SERVICE_NAME,
        )
    except Exception as exc:
        return EvaluateAnswerResult(
            ok=False,
            response=None,
            error=safe_user_message(exc),
            guardrails=guards,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            evaluation=None,
        )

    # --- Output pipeline ---
    output_check = run_output_pipeline(resp.text, service=_SERVICE_NAME)
    if not output_check.safe:
        return EvaluateAnswerResult(
            ok=False,
            response=None,
            error=output_check.reason or "Model output rejected.",
            guardrails=guards,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            evaluation=None,
        )

    safe_resp = LLMResponse(
        text=output_check.text,
        model=resp.model,
        usage=resp.usage,
        raw_response_id=resp.raw_response_id,
        latency_ms=resp.latency_ms,
        provider=resp.provider,
    )

    evaluation = None
    if safe_resp.text:
        evaluation = _parse_evaluation_response(safe_resp.text)

    return EvaluateAnswerResult(
        ok=True,
        response=safe_resp,
        error=None,
        guardrails=guards,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        evaluation=evaluation,
    )


def _evaluator_system_prompt(
    *,
    response_language: str = "en",
    persona: str = "Hiring Manager",
    prompt_strategy: str | None = None,
) -> str:
    rubric = get_persona_evaluation_rubric(persona)
    base = (
        "You are an expert interviewer evaluating a live mock-interview response. "
        "Be specific, professional, and actionable. Apply the persona rubric consistently."
        "\n\n"
        "Output format (use these exact section headers for parsing):\n"
        "## Overall score\n"
        "A single integer 0-10 (overall).\n"
        "## Technical Accuracy\n"
        "2-4 sentences; may include a sub-score like (7/10) if helpful.\n"
        "## Clarity\n"
        "1-3 sentences.\n"
        "## Depth\n"
        "1-3 sentences.\n"
        "## Communication\n"
        "1-3 sentences (structure, precision, listening to the question).\n"
        "## Strengths\n"
        "Bullet list of what the candidate did well.\n"
        "## Improvements\n"
        "Bullet list of concrete improvements or missing elements.\n"
        "## Better / Model Answer\n"
        "A concise model answer (3-6 sentences).\n"
        "## Next Follow-up Question\n"
        "Exactly ONE follow-up interview question on the next line (no bullets). "
        "It should feel like a natural continuation of this mock interview and, when candidate topics "
        "are provided, MUST drill into those specifics (tools, architecture, trade-offs, testing, ops).\n"
        "\n"
        "Legacy compatibility: you may also include optional sections ## Criteria met and "
        "## Criteria missing / Gaps if you already wrote bullets under Strengths/Improvements.\n"
    )
    persona_fragment = get_persona_prompt(persona)
    strategy_note = (
        f"\n\n{evaluation_coaching_directive(prompt_strategy)}" if prompt_strategy else ""
    )
    return (
        f"{base}\n\nInterviewer persona: {persona_fragment}\n\nPersona rubric (grading + follow-ups):\n{rubric}"
        f"{strategy_note}\n\n{language_instruction(response_language)}"
    )


def _evaluator_user_prompt(
    *,
    role_category: str,
    role_title: str,
    seniority: str,
    interview_round: str,
    interview_focus: str,
    effective_difficulty: str,
    job_description: str,
    question: str,
    answer: str,
    candidate_topics: list[str],
    evaluation_context_hints: str,
) -> str:
    jd_block = (
        f"\nJob description (optional):\n{job_description}\n"
        if (job_description or "").strip()
        else ""
    )
    topics_block = ""
    if candidate_topics:
        topics_block = (
            "\nCandidate topics mentioned (use for Next Follow-up Question):\n- "
            + "\n- ".join(candidate_topics[:20])
        )
    hints_block = (
        f"\nFollow-up instruction:\n{evaluation_context_hints}\n"
        if evaluation_context_hints
        else ""
    )
    return (
        f"Role category: {role_category}\n"
        f"Role title: {role_title}\n"
        f"Seniority: {seniority}\n"
        f"Interview round: {interview_round}\n"
        f"Interview focus: {interview_focus}\n"
        f"Calibrated difficulty: {effective_difficulty}\n"
        f"{jd_block}{topics_block}{hints_block}\n"
        "Question:\n"
        f"{question}\n\n"
        "Candidate answer:\n"
        f"{answer}\n"
    )


def _parse_evaluation_response(text: str) -> EvaluationResult | None:
    """Parse markdown-style sections from evaluator output into EvaluationResult."""
    text = (text or "").strip()
    if not text:
        return None

    def section(name: str) -> str:
        # Match ## Name or ## Name (case-insensitive) and take content until next ## or end
        pat = re.compile(
            rf"##\s*{re.escape(name)}\s*\n(.*?)(?=\n##\s|\Z)",
            re.DOTALL | re.IGNORECASE,
        )
        m = pat.search(text)
        return (m.group(1).strip() if m else "").strip()

    def bullets(block: str) -> list[str]:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        out = []
        for line in lines:
            for prefix in ("- ", "* ", "• ", "1. ", "2. ", "3. "):
                if line.startswith(prefix):
                    line = line[len(prefix) :].strip()
                    break
            if line:
                out.append(line)
        return out

    score_str = section("Overall score") or section("Score")
    score = 0
    for part in score_str.replace(".", " ").split():
        if part.isdigit():
            score = min(10, max(0, int(part)))
            break

    technical_accuracy = section("Technical Accuracy")
    clarity = section("Clarity")
    depth = section("Depth")
    communication = section("Communication")
    strengths = bullets(section("Strengths"))
    improvements = bullets(section("Improvements"))
    criteria_met = bullets(section("Criteria met")) or list(strengths)
    criteria_missing = (
        bullets(section("Criteria missing / Gaps"))
        or bullets(section("Gaps"))
        or list(improvements)
    )
    critique = section("Critique")
    improved = section("Better / Model Answer") or section("Improved answer")
    next_block = section("Next Follow-up Question")
    next_fu = next_block.splitlines()[0].strip() if next_block else ""
    follow_up_block = section("Follow-up questions")
    follow_ups = bullets(follow_up_block)
    if next_fu:
        follow_ups = [next_fu] + [x for x in follow_ups if x != next_fu]
    if len(follow_ups) > 3:
        follow_ups = follow_ups[:3]
    if not strengths and criteria_met:
        strengths = list(criteria_met)
    if not improvements and criteria_missing:
        improvements = list(criteria_missing)

    return EvaluationResult(
        score=score,
        technical_accuracy=technical_accuracy,
        clarity=clarity,
        depth=depth,
        communication=communication,
        strengths=strengths,
        improvements=improvements,
        criteria_met=criteria_met,
        criteria_missing=criteria_missing,
        critique=critique,
        improved_answer=improved,
        next_follow_up_question=next_fu,
        follow_ups=follow_ups,
    )
