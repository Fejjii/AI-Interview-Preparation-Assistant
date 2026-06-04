"""Mock interview FSM: classification, evaluation gating, and chat routing."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from interview_app.app.ui_settings import UISettings
from interview_app.security.pipeline import InputPipelineResult
from interview_app.services.answer_evaluator import EvaluateAnswerResult
from interview_app.services.chat_service import run_turn
from interview_app.services.interview_generator import GenerateQuestionsResult
from interview_app.services.mock_interview_flow import (
    InterviewState,
    UserMessageKind,
    UserTurnType,
    classify_user_message,
    detect_user_turn_type,
    extract_candidate_topics,
    should_evaluate,
    should_run_evaluation,
    should_run_full_evaluation,
)
from interview_app.utils.types import ChatMessage, EvaluationResult, LLMResponse


def _settings(**kwargs: object) -> UISettings:
    fields: dict[str, object] = {
        "role_category": "Other",
        "role_title": "Engineer",
        "seniority": "Mid-Level",
        "interview_round": "Technical Interview",
        "interview_focus": "Technical Knowledge",
        "job_description": "",
        "persona": "Hiring Manager",
        "question_difficulty_mode": "Auto",
        "effective_question_difficulty": "Medium",
        "prompt_strategy": "chain_of_thought",
        "model_preset": "gpt-4o-mini",
        "temperature": 0.15,
        "top_p": 0.95,
        "max_tokens": 900,
        "show_debug": False,
        "response_language": "en",
        "usage_mode": "demo",
        "byo_key_hint": None,
    }
    fields.update(kwargs)
    return UISettings(**fields)  # type: ignore[arg-type]


@pytest.fixture
def input_pipeline_ok() -> None:
    with patch(
        "interview_app.services.chat_service.run_input_pipeline",
        return_value=InputPipelineResult(ok=True),
    ):
        yield


def test_classify_greeting() -> None:
    assert classify_user_message("Hello") == UserMessageKind.GREETING


def test_classify_lets_start() -> None:
    assert classify_user_message("Let's start") == UserMessageKind.START_REQUEST


def test_classify_starter_instruction() -> None:
    assert (
        classify_user_message("Start a mock interview for backend preparation")
        == UserMessageKind.START_REQUEST
    )


def test_greeting_should_not_trigger_evaluation_even_with_pending() -> None:
    assert (
        should_run_evaluation(
            pending_question="Describe REST.",
            kind=UserMessageKind.GREETING,
            user_text="Hi",
        )
        is False
    )


def test_first_real_answer_triggers_evaluation_when_pending() -> None:
    text = (
        "In my last role I built a distributed cache using Redis because reads dominated "
        "and we needed sub-millisecond p99 latency for the product catalog."
    )
    assert (
        should_run_evaluation(
            pending_question="How would you scale reads?",
            kind=UserMessageKind.CANDIDATE_ANSWER,
            user_text=text,
        )
        is True
    )


def test_run_turn_hello_does_not_call_evaluate_answer(
    input_pipeline_ok: None,
) -> None:
    ok_question = GenerateQuestionsResult(
        ok=True,
        response=LLMResponse(
            text="1. Describe a tough debugging session.",
            model="gpt-4o-mini",
            usage=None,
            raw_response_id=None,
        ),
        error=None,
        guardrails={},
        prompt=None,
    )
    with patch("interview_app.services.chat_service.generate_questions", return_value=ok_question):
        with patch("interview_app.services.chat_service.evaluate_answer") as ev:
            session: dict = {}
            msgs = [ChatMessage(role="user", content="Hello")]
            out = run_turn(_settings(), msgs, session_state=session)

    ev.assert_not_called()
    assert "Describe" in out.assistant_message
    assert session.get("ia_mock_pending_question")


def test_run_turn_lets_start_does_not_call_evaluate_answer(
    input_pipeline_ok: None,
) -> None:
    ok_question = GenerateQuestionsResult(
        ok=True,
        response=LLMResponse(
            text="1. Explain eventual consistency.",
            model="gpt-4o-mini",
            usage=None,
            raw_response_id=None,
        ),
        error=None,
        guardrails={},
        prompt=None,
    )
    with patch("interview_app.services.chat_service.generate_questions", return_value=ok_question):
        with patch("interview_app.services.chat_service.evaluate_answer") as ev:
            session: dict = {}
            msgs = [ChatMessage(role="user", content="I'm ready")]
            run_turn(_settings(), msgs, session_state=session)
    ev.assert_not_called()


def test_run_turn_answer_after_question_calls_evaluate_and_sets_next_pending(
    input_pipeline_ok: None,
) -> None:
    ev = EvaluateAnswerResult(
        ok=True,
        response=LLMResponse(text="graded", model="gpt-4o-mini", usage=None, raw_response_id=None),
        error=None,
        guardrails={},
        system_prompt="sys",
        user_prompt="user",
        evaluation=EvaluationResult(
            score=8,
            criteria_met=["clear"],
            criteria_missing=["metrics"],
            critique="Add numbers.",
            improved_answer="Better.",
            follow_ups=["How would you monitor it?"],
        ),
    )
    with patch("interview_app.services.chat_service.evaluate_answer", return_value=ev):
        session = {
            "ia_mock_pending_question": "What is the CAP theorem?",
            "ia_mock_phase": "awaiting_answer",
        }
        msgs = [
            ChatMessage(role="user", content="Let's start"),
            ChatMessage(role="assistant", content="Placeholder"),
            ChatMessage(
                role="user",
                content=(
                    "CAP is consistency, availability, and partition tolerance — in partitions "
                    "you typically choose between C and A because perfect network assumptions fail."
                ),
            ),
        ]
        out = run_turn(_settings(), msgs, session_state=session)

    assert "Score" in out.assistant_message
    assert session.get("ia_mock_pending_question") == "How would you monitor it?"


def test_switch_to_behavioral_skips_evaluation_and_sets_behavioral_focus(
    input_pipeline_ok: None,
) -> None:
    ok_question = GenerateQuestionsResult(
        ok=True,
        response=LLMResponse(
            text="1. Tell me about stakeholder conflict.",
            model="gpt-4o-mini",
            usage=None,
            raw_response_id=None,
        ),
        error=None,
        guardrails={},
        prompt=None,
    )
    with patch(
        "interview_app.services.chat_service.generate_questions",
        return_value=ok_question,
    ) as gen:
        with patch("interview_app.services.chat_service.evaluate_answer") as ev:
            session = {
                "ia_mock_pending_question": "Prior question text",
                "ia_mock_phase": "awaiting_answer",
            }
            msgs = [
                ChatMessage(role="user", content="Hi"),
                ChatMessage(role="assistant", content="Coach intro"),
                ChatMessage(role="user", content="Can we switch to behavioral questions?"),
            ]
            run_turn(_settings(interview_focus="Technical Knowledge"), msgs, session_state=session)

    ev.assert_not_called()
    assert gen.call_args.kwargs.get("interview_focus") == "Behavioral / Soft Skills"


def test_ready_phrase_i_am_ready_classifies_as_start() -> None:
    assert (
        classify_user_message("Hello, I am ready for the interview")
        == UserMessageKind.START_REQUEST
    )


def test_clarification_turn_never_evaluates_even_when_waiting() -> None:
    text = "Before I answer, can you clarify if this interview is more theoretical or practical?"
    assert (
        detect_user_turn_type(text, pending_question="Why PostgreSQL?")
        == UserTurnType.CLARIFICATION
    )
    assert (
        should_run_full_evaluation(
            pending_question="Why PostgreSQL?",
            turn_type=UserTurnType.CLARIFICATION,
            interview_state=InterviewState.WAITING_FOR_ANSWER,
            user_text=text,
        )
        is False
    )
    assert should_evaluate(UserTurnType.CLARIFICATION, InterviewState.WAITING_FOR_ANSWER) is False


def test_extract_topics_from_engineering_answer() -> None:
    ans = "We migrated from Redshift to Snowflake and modeled incremental dbt runs for late-arriving events."
    topics = extract_candidate_topics(ans)
    assert any("snowflake" in t.lower() for t in topics)
    assert any("dbt" in t.lower() for t in topics)


def test_restart_resets_pending_question(input_pipeline_ok: None) -> None:
    ok_question = GenerateQuestionsResult(
        ok=True,
        response=LLMResponse(
            text="1. Fresh question.",
            model="gpt-4o-mini",
            usage=None,
            raw_response_id=None,
        ),
        error=None,
        guardrails={},
        prompt=None,
    )
    with patch("interview_app.services.chat_service.generate_questions", return_value=ok_question):
        session = {"ia_mock_pending_question": "Stale", "ia_mock_phase": "awaiting_answer"}
        msgs = [
            ChatMessage(role="user", content="hi"),
            ChatMessage(role="assistant", content="hello"),
            ChatMessage(role="user", content="restart the interview"),
        ]
        run_turn(_settings(), msgs, session_state=session)

    assert session.get("ia_mock_pending_question") != "Stale"
