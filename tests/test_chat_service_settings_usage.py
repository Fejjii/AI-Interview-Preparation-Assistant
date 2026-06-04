"""Sidebar settings are forwarded into mock-interview LLM calls."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from interview_app.app.ui_settings import UISettings
from interview_app.security.pipeline import InputPipelineResult
from interview_app.services.answer_evaluator import EvaluateAnswerResult
from interview_app.services.chat_service import run_turn
from interview_app.services.interview_generator import GenerateQuestionsResult
from interview_app.utils.types import ChatMessage, EvaluationResult, LLMResponse


def _settings() -> UISettings:
    return UISettings(
        role_category="Software Engineering",
        role_title="Backend Engineer",
        seniority="Senior",
        interview_round="System Design Interview",
        interview_focus="System Design / Architecture",
        job_description="JD",
        persona="Bar Raiser (Strict)",
        question_difficulty_mode="Auto",
        effective_question_difficulty="Hard",
        prompt_strategy="few_shot",
        model_preset="gpt-4o-mini",
        temperature=0.42,
        top_p=0.88,
        max_tokens=1200,
        show_debug=False,
        response_language="en",
        usage_mode="demo",
        byo_key_hint=None,
    )


@pytest.fixture
def input_pipeline_ok() -> None:
    with patch(
        "interview_app.services.chat_service.run_input_pipeline",
        return_value=InputPipelineResult(ok=True),
    ):
        yield


def test_generate_questions_receives_model_temperature_top_p_max_tokens_and_strategy(
    input_pipeline_ok: None,
) -> None:
    ok_question = GenerateQuestionsResult(
        ok=True,
        response=LLMResponse(
            text="1. One question.", model="gpt-4o-mini", usage=None, raw_response_id=None
        ),
        error=None,
        guardrails={},
        prompt=None,
    )
    secret = "sk-unit123456789012345678901234567890"
    with patch(
        "interview_app.services.chat_service.generate_questions",
        return_value=ok_question,
    ) as gen:
        session: dict = {}
        msgs = [ChatMessage(role="user", content="Let's start")]
        run_turn(_settings(), msgs, session_state=session, openai_api_key=secret)

    kwargs = gen.call_args.kwargs
    assert kwargs["role_category"] == "Software Engineering"
    assert kwargs["role_title"] == "Backend Engineer"
    assert kwargs["seniority"] == "Senior"
    assert kwargs["interview_round"] == "System Design Interview"
    assert kwargs["interview_focus"] == "System Design / Architecture"
    assert kwargs["prompt_strategy"] == "few_shot"
    assert kwargs["model"] == "gpt-4o-mini"
    assert kwargs["temperature"] == 0.42
    assert kwargs["top_p"] == 0.88
    assert kwargs["max_tokens"] == 1200
    assert kwargs["persona"] == "Bar Raiser (Strict)"
    assert kwargs["difficulty"] == "Hard"
    assert kwargs["openai_api_key"] == secret


def test_evaluate_answer_receives_settings_and_prompt_strategy(
    input_pipeline_ok: None,
) -> None:
    ok_question = GenerateQuestionsResult(
        ok=True,
        response=LLMResponse(text="1. Q1", model="gpt-4o-mini", usage=None, raw_response_id=None),
        error=None,
        guardrails={},
        prompt=None,
    )
    ev = EvaluateAnswerResult(
        ok=True,
        response=LLMResponse(text="graded", model="gpt-4o-mini", usage=None, raw_response_id=None),
        error=None,
        guardrails={},
        system_prompt="s",
        user_prompt="u",
        evaluation=EvaluationResult(
            score=6,
            criteria_met=[],
            criteria_missing=[],
            critique="",
            improved_answer="",
            follow_ups=["Follow up?"],
        ),
    )
    with patch("interview_app.services.chat_service.generate_questions", return_value=ok_question):
        with patch("interview_app.services.chat_service.evaluate_answer", return_value=ev) as ev_fn:
            session = {"ia_mock_pending_question": "Design a URL shortener"}
            msgs = [
                ChatMessage(role="user", content="start"),
                ChatMessage(role="assistant", content="x"),
                ChatMessage(
                    role="user",
                    content=(
                        "I would use a base62-encoded key, store mappings in a sharded key-value store, "
                        "and redirect via edge caches to minimize latency while handling hot keys."
                    ),
                ),
            ]
            run_turn(_settings(), msgs, session_state=session)

    kw = ev_fn.call_args.kwargs
    assert kw["interview_round"] == "System Design Interview"
    assert kw["interview_focus"] == "System Design / Architecture"
    assert kw["persona"] == "Bar Raiser (Strict)"
    assert kw["prompt_strategy"] == "few_shot"
    assert kw["model"] == "gpt-4o-mini"
    assert kw["temperature"] == 0.42
    assert kw["top_p"] == 0.88
    assert kw["max_tokens"] == 1200
    assert kw["question"] == "Design a URL shortener"
    assert isinstance(kw.get("candidate_topics"), list)
    assert kw.get("evaluation_context_hints") is not None
