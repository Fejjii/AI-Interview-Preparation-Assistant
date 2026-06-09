from __future__ import annotations

"""
Service: generate interview questions.

This module is the "domain layer" for the Question generation tab.
It translates UI inputs into:
- validated/sanitized text (guardrails via the security pipeline)
- a chosen prompt strategy (prompt-building)
- a single OpenAI call (LLM client)

The Streamlit UI calls `generate_questions(...)` directly and then renders either:
- a blocked request (guardrail failure), or
- an `LLMResponse` with optional prompt debug output.
"""

from dataclasses import dataclass
from typing import Any, Callable

from interview_app.app.interview_form_config import truncate_job_description, validate_role_title
from interview_app.app.ui_settings import UISettings
from interview_app.app.usage_mode import maybe_block_demo_llm_call, record_demo_llm_call
from interview_app.llm.model_settings import resolve_openai_model_id
from interview_app.llm.openai_client import LLMClient
from interview_app.prompts import prompt_strategies
from interview_app.prompts.prompt_strategies import PromptBuildResult
from interview_app.security.guards import GuardrailResult, protect_system_prompt
from interview_app.security.pipeline import run_input_pipeline, run_output_pipeline
from interview_app.utils.errors import safe_user_message
from interview_app.utils.types import LLMResponse

_SERVICE_NAME = "interview_generator"


@dataclass(frozen=True)
class GenerateQuestionsResult:
    """Return type for `generate_questions` (easy to consume from Streamlit)."""

    ok: bool
    response: LLMResponse | None
    error: str | None
    guardrails: dict[str, GuardrailResult]
    prompt: PromptBuildResult | None


def generate_questions(
    *,
    role_category: str,
    role_title: str,
    seniority: str,
    interview_round: str,
    interview_focus: str,
    job_description: str,
    n_questions: int,
    prompt_strategy: str,
    model: str,
    temperature: float,
    max_tokens: int,
    top_p: float | None = None,
    response_language: str = "en",
    difficulty: str = "Medium",
    persona: str = "Hiring Manager",
    session_state: dict[str, Any] | None = None,
    skip_session_rate_limit: bool = False,
    openai_api_key: str | None = None,
    mock_interview_context_suffix: str = "",
) -> GenerateQuestionsResult:
    """
    Generate interview questions using a selected prompt strategy.

    This is the main "happy path" service used by the Streamlit UI.

    When ``skip_session_rate_limit`` is True, the session rate-limit step is skipped for
    this service (e.g. chat already consumed one unit for the same user-visible turn).

    ``mock_interview_context_suffix`` is appended to the user prompt when non-empty (mock
    interview only): candidate tools/projects for context-aware follow-up questions.
    """

    guards: dict[str, GuardrailResult] = {}

    ok_title, role_trimmed = validate_role_title(role_title)
    if not ok_title:
        return GenerateQuestionsResult(
            ok=False,
            response=None,
            error="Please enter a role title.",
            guardrails=guards,
            prompt=None,
        )

    # --- Input pipeline: validation + sanitization + moderation + rate limit ---
    role_pipe = run_input_pipeline(
        role_trimmed,
        field_name="role_title",
        max_chars=200,
        session_state=session_state,
        check_rate=not skip_session_rate_limit,
        service=_SERVICE_NAME,
    )
    if role_pipe.guardrail:
        guards["role_title"] = role_pipe.guardrail
    if not role_pipe.ok:
        return GenerateQuestionsResult(
            ok=False,
            response=None,
            error=role_pipe.error or "Invalid role title.",
            guardrails=guards,
            prompt=None,
        )

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
        return GenerateQuestionsResult(
            ok=False,
            response=None,
            error=jd_pipe.error or "Job description rejected by guardrails.",
            guardrails=guards,
            prompt=None,
        )

    prompt = _build_prompt(
        prompt_strategy=prompt_strategy,
        role_category=role_category,
        role_title=role_pipe.cleaned_text,
        seniority=seniority,
        interview_round=interview_round,
        interview_focus=interview_focus,
        job_description=jd_pipe.cleaned_text if jd_text else "",
        n_questions=n_questions,
        response_language=response_language,
        difficulty=difficulty,
        persona=persona,
    )

    system_prompt = protect_system_prompt(prompt.system_prompt)
    user_prompt_body = prompt.user_prompt.rstrip()
    suffix = (mock_interview_context_suffix or "").strip()
    if suffix:
        user_prompt_body = (
            f"{user_prompt_body}\n\n---\nAdditional instructions for this request:\n{suffix}\n"
        )

    blocked = maybe_block_demo_llm_call(session_state)
    if blocked:
        return GenerateQuestionsResult(
            ok=False,
            response=None,
            error=blocked,
            guardrails=guards,
            prompt=None,
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
            user_prompt=user_prompt_body,
            top_p=top_p,
            temperature=temperature,
            max_tokens=max_tokens,
            model=resolve_openai_model_id(model),
            llm_route=_SERVICE_NAME,
        )
    except Exception as exc:
        return GenerateQuestionsResult(
            ok=False,
            response=None,
            error=safe_user_message(exc),
            guardrails=guards,
            prompt=None,
        )

    record_demo_llm_call(session_state)

    # --- Output pipeline: validate model response ---
    output_check = run_output_pipeline(resp.text, service=_SERVICE_NAME)
    if not output_check.safe:
        return GenerateQuestionsResult(
            ok=False,
            response=None,
            error=output_check.reason or "Model output rejected.",
            guardrails=guards,
            prompt=None,
        )

    safe_resp = LLMResponse(
        text=output_check.text,
        model=resp.model,
        usage=resp.usage,
        raw_response_id=resp.raw_response_id,
        latency_ms=resp.latency_ms,
        provider=resp.provider,
    )

    return GenerateQuestionsResult(
        ok=True,
        response=safe_resp,
        error=None,
        guardrails=guards,
        prompt=PromptBuildResult(
            system_prompt=system_prompt,
            user_prompt=user_prompt_body,
            template_name=prompt.template_name,
            debug_trace=prompt.debug_trace,
        ),
    )


def _build_prompt(
    *,
    prompt_strategy: str,
    role_category: str,
    role_title: str,
    seniority: str,
    interview_round: str,
    interview_focus: str,
    job_description: str,
    n_questions: int,
    response_language: str = "en",
    difficulty: str = "Medium",
    persona: str = "Hiring Manager",
) -> PromptBuildResult:
    """
    Dispatch to the correct prompt-builder function by strategy name.
    """
    builders: dict[str, Callable[..., PromptBuildResult]] = {
        "zero_shot": prompt_strategies.build_zero_shot_prompt,
        "few_shot": prompt_strategies.build_few_shot_prompt,
        "chain_of_thought": prompt_strategies.build_chain_of_thought_prompt,
        "structured_output": prompt_strategies.build_structured_output_prompt,
        "role_based": prompt_strategies.build_role_based_prompt,
    }
    builder = builders.get(prompt_strategy)
    if builder is None:
        raise ValueError(f"Unknown prompt strategy: {prompt_strategy!r}")

    return builder(
        role_category=role_category,
        role_title=role_title,
        seniority=seniority,
        interview_round=interview_round,
        interview_focus=interview_focus,
        job_description=job_description,
        n_questions=n_questions,
        response_language=response_language,
        difficulty=difficulty,
        persona=persona,
    )


def generate_questions_from_settings(
    *,
    settings: UISettings,
    prompt_strategy: str,
    n_questions: int,
    session_state: dict[str, Any] | None = None,
    skip_session_rate_limit: bool = False,
    response_language: str | None = None,
    openai_api_key: str | None = None,
) -> GenerateQuestionsResult:
    """
    Thin wrapper: map ``UISettings`` into ``generate_questions`` for a chosen strategy.

    Used by the Streamlit layout (single run + comparison mode) without duplicating
    parameter wiring.

    ``response_language`` overrides ``settings.response_language`` when set (e.g. after
    auto-detection from the job description in session state).
    """
    lang = response_language if response_language is not None else settings.response_language
    return generate_questions(
        role_category=settings.role_category,
        role_title=settings.role_title,
        seniority=settings.seniority,
        interview_round=settings.interview_round,
        interview_focus=settings.interview_focus,
        job_description=settings.job_description,
        n_questions=n_questions,
        prompt_strategy=prompt_strategy,
        model=settings.model_preset,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        top_p=settings.top_p,
        response_language=lang,
        difficulty=settings.effective_question_difficulty,
        persona=settings.persona,
        session_state=session_state,
        skip_session_rate_limit=skip_session_rate_limit,
        openai_api_key=openai_api_key,
    )
