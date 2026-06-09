"""Per-session demo LLM usage limits (Demo access mode only)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from interview_app.app.usage_mode import (
    DEMO_LIMIT_MESSAGE,
    KEY_DEMO_LLM_CALL_COUNT,
    KEY_USAGE_MODE,
    UsageMode,
    demo_remaining_calls,
    demo_usage_limit_reached,
    get_demo_usage_count,
    increment_demo_usage_count,
    maybe_block_demo_llm_call,
    record_demo_llm_call,
)
from interview_app.config.settings import Settings, get_settings
from interview_app.security.guards import GuardrailResult
from interview_app.services.answer_evaluator import evaluate_answer
from interview_app.services.interview_generator import generate_questions
from interview_app.utils.types import LLMResponse


def _demo_session(count: int = 0) -> dict[str, object]:
    return {KEY_USAGE_MODE: UsageMode.DEMO.value, KEY_DEMO_LLM_CALL_COUNT: count}


def _byo_session(count: int = 0) -> dict[str, object]:
    return {KEY_USAGE_MODE: UsageMode.BYO.value, KEY_DEMO_LLM_CALL_COUNT: count}


def test_settings_demo_max_llm_calls_default() -> None:
    settings = Settings(_env_file=None)
    assert settings.demo_max_llm_calls_per_session == 10


def test_settings_demo_max_llm_calls_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_MAX_LLM_CALLS_PER_SESSION", "3")
    get_settings.cache_clear()
    assert get_settings().demo_max_llm_calls_per_session == 3


def test_demo_counter_increments_only_in_demo_mode() -> None:
    demo = _demo_session()
    byo = _byo_session()

    assert increment_demo_usage_count(demo) == 1
    assert get_demo_usage_count(demo) == 1
    assert increment_demo_usage_count(byo) == 0
    assert get_demo_usage_count(byo) == 0


def test_demo_remaining_calls_and_limit_reached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_MAX_LLM_CALLS_PER_SESSION", "2")
    get_settings.cache_clear()

    ss = _demo_session(1)
    assert demo_remaining_calls(ss) == 1
    assert demo_usage_limit_reached(ss) is False

    ss[KEY_DEMO_LLM_CALL_COUNT] = 2
    assert demo_remaining_calls(ss) == 0
    assert demo_usage_limit_reached(ss) is True
    assert maybe_block_demo_llm_call(ss) == DEMO_LIMIT_MESSAGE


def test_byo_mode_never_blocked_by_demo_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_MAX_LLM_CALLS_PER_SESSION", "1")
    get_settings.cache_clear()

    ss = _byo_session(99)
    assert maybe_block_demo_llm_call(ss) is None
    assert demo_remaining_calls(ss) is None


def test_limit_message_is_user_friendly() -> None:
    assert "Demo usage limit reached" in DEMO_LIMIT_MESSAGE
    assert "refresh later" in DEMO_LIMIT_MESSAGE
    assert "own OpenAI API key" in DEMO_LIMIT_MESSAGE


def test_generate_questions_blocks_demo_at_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_MAX_LLM_CALLS_PER_SESSION", "1")
    get_settings.cache_clear()

    ss = _demo_session(1)
    result = generate_questions(
        role_category="Other",
        role_title="Engineer",
        seniority="Mid-Level",
        interview_round="Technical Interview",
        interview_focus="Behavioral / Soft Skills",
        job_description="",
        n_questions=1,
        prompt_strategy="zero_shot",
        model="gpt-4o-mini",
        temperature=0.2,
        max_tokens=400,
        session_state=ss,
        openai_api_key=None,
    )
    assert result.ok is False
    assert result.error == DEMO_LIMIT_MESSAGE
    assert get_demo_usage_count(ss) == 1


def test_generate_questions_increments_demo_counter_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEMO_MAX_LLM_CALLS_PER_SESSION", "5")
    get_settings.cache_clear()

    ss = _demo_session(0)
    resp = LLMResponse(
        text="1. Sample question?", model="gpt-4o-mini", usage=None, raw_response_id=None
    )
    with patch("interview_app.services.interview_generator.LLMClient") as mock_cls:
        mock_cls.return_value.generate_response.return_value = resp
        result = generate_questions(
            role_category="Other",
            role_title="Engineer",
            seniority="Mid-Level",
            interview_round="Technical Interview",
            interview_focus="Behavioral / Soft Skills",
            job_description="",
            n_questions=1,
            prompt_strategy="zero_shot",
            model="gpt-4o-mini",
            temperature=0.2,
            max_tokens=400,
            session_state=ss,
            openai_api_key=None,
        )

    assert result.ok is True
    assert get_demo_usage_count(ss) == 1
    mock_cls.return_value.generate_response.assert_called_once()


def test_generate_questions_byo_does_not_increment_demo_counter() -> None:
    ss = _byo_session(0)
    resp = LLMResponse(
        text="1. Sample question?", model="gpt-4o-mini", usage=None, raw_response_id=None
    )
    with patch("interview_app.services.interview_generator.LLMClient") as mock_cls:
        mock_cls.return_value.generate_response.return_value = resp
        result = generate_questions(
            role_category="Other",
            role_title="Engineer",
            seniority="Mid-Level",
            interview_round="Technical Interview",
            interview_focus="Behavioral / Soft Skills",
            job_description="",
            n_questions=1,
            prompt_strategy="zero_shot",
            model="gpt-4o-mini",
            temperature=0.2,
            max_tokens=400,
            session_state=ss,
            openai_api_key="sk-12345678901234567890123456789012",
        )

    assert result.ok is True
    assert get_demo_usage_count(ss) == 0


def test_guardrail_blocked_request_does_not_increment_demo_counter() -> None:
    ss = _demo_session(0)
    with patch("interview_app.services.interview_generator.run_input_pipeline") as mock_pipe:
        mock_pipe.return_value.ok = False
        mock_pipe.return_value.error = "Input rejected."
        mock_pipe.return_value.guardrail = GuardrailResult(
            ok=False,
            cleaned_text="",
            reason="blocked",
            flags=["injection"],
        )
        with patch("interview_app.services.interview_generator.LLMClient") as mock_cls:
            result = generate_questions(
                role_category="Other",
                role_title="Engineer",
                seniority="Mid-Level",
                interview_round="Technical Interview",
                interview_focus="Behavioral / Soft Skills",
                job_description="",
                n_questions=1,
                prompt_strategy="zero_shot",
                model="gpt-4o-mini",
                temperature=0.2,
                max_tokens=400,
                session_state=ss,
                openai_api_key=None,
            )

    assert result.ok is False
    assert get_demo_usage_count(ss) == 0
    mock_cls.assert_not_called()


def test_evaluate_answer_blocks_demo_at_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_MAX_LLM_CALLS_PER_SESSION", "2")
    get_settings.cache_clear()

    ss = _demo_session(2)
    result = evaluate_answer(
        role_category="Other",
        role_title="Engineer",
        seniority="Mid-Level",
        interview_round="Technical Interview",
        interview_focus="Behavioral / Soft Skills",
        effective_difficulty="Medium",
        question="What is REST?",
        answer="Representational state transfer.",
        model="gpt-4o-mini",
        temperature=0.2,
        max_tokens=400,
        session_state=ss,
        openai_api_key=None,
    )
    assert result.ok is False
    assert result.error == DEMO_LIMIT_MESSAGE


def test_record_demo_llm_call_helper() -> None:
    ss = _demo_session(0)
    record_demo_llm_call(ss)
    record_demo_llm_call(None)
    assert get_demo_usage_count(ss) == 1
