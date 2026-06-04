"""Mock interview: effective config, turn detection, contextual evaluation, multi-turn stability."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from interview_app.app.ui_settings import UISettings
from interview_app.security.pipeline import InputPipelineResult
from interview_app.services.answer_evaluator import EvaluateAnswerResult
from interview_app.services.chat_service import run_turn
from interview_app.services.context_extractor import extract_interview_topics
from interview_app.services.context_manager import (
    get_session_interview_context,
    merge_message_into_session_context,
    set_active_interview_question,
)
from interview_app.services.effective_interview_config import get_effective_interview_config
from interview_app.services.interview_generator import GenerateQuestionsResult
from interview_app.services.mock_interview_flow import (
    MockInterviewTurnKind,
    UserTurnType,
    detect_mock_interview_turn_kind,
    detect_user_turn_type,
)
from interview_app.utils.types import ChatMessage, EvaluationResult, LLMResponse, SessionMeta


def _settings(**kwargs: object) -> UISettings:
    fields: dict[str, object] = {
        "role_category": "Data Engineering",
        "role_title": "Data Engineer",
        "seniority": "Senior",
        "interview_round": "Technical Interview",
        "interview_focus": "Technical Knowledge",
        "job_description": "",
        "persona": "Technical Interviewer",
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


def test_effective_config_falls_back_to_session_meta_role() -> None:
    settings = _settings(role_title="")
    meta = SessionMeta(
        role_title="data engineer",
        role_category="Data Engineering",
        seniority="Senior",
        interview_round="Technical Interview",
        interview_focus="Technical Knowledge",
        persona="Technical Interviewer",
    )
    eff = get_effective_interview_config(settings, {"session_meta": meta})
    assert eff.role_title == "data engineer"
    assert eff.role_category == "Data Engineering"


def test_extract_migration_message_topics() -> None:
    msg = (
        "I migrated a legacy data warehouse to Snowflake and used dbt incremental models "
        "to reduce runtime by 40%."
    )
    topics = extract_interview_topics(msg)
    tools_l = " ".join(x.lower() for x in topics["tools"])
    assert "snowflake" in tools_l
    assert "dbt" in tools_l
    assert any("incremental" in c.lower() for c in topics["concepts"])
    assert any("migration" in p.lower() for p in topics["projects"])
    assert topics["achievements"]


def test_project_story_without_question_overlap_is_experience_not_answer() -> None:
    msg = (
        "I migrated a legacy data warehouse to Snowflake and used dbt incremental models "
        "to reduce runtime by 40%."
    )
    assert (
        detect_user_turn_type(msg, pending_question="What is the CAP theorem?")
        == UserTurnType.EXPERIENCE
    )
    assert (
        detect_mock_interview_turn_kind(msg, "What is the CAP theorem?", None)
        == MockInterviewTurnKind.PROJECT_EXPERIENCE_STATEMENT
    )


def test_project_story_with_overlap_still_counts_as_answer() -> None:
    msg = (
        "I migrated a legacy data warehouse to Snowflake and used dbt incremental models "
        "to reduce runtime by 40%."
    )
    assert (
        detect_user_turn_type(msg, pending_question="How would you use dbt on Snowflake?")
        == UserTurnType.ANSWER
    )


def test_request_contextual_turn_kind() -> None:
    msg = "Can you ask me a question related to that project?"
    assert (
        detect_mock_interview_turn_kind(msg, "Any pending question?", None)
        == MockInterviewTurnKind.REQUEST_CONTEXTUAL_QUESTION
    )
    assert (
        detect_user_turn_type(msg, pending_question="Any pending question?")
        == UserTurnType.CONTEXTUAL_QUESTION_REQUEST
    )


def test_run_turn_related_question_uses_session_meta_role(input_pipeline_ok: None) -> None:
    ok_question = GenerateQuestionsResult(
        ok=True,
        response=LLMResponse(
            text="1. How did you validate incremental dbt models after the Snowflake cutover?",
            model="gpt-4o-mini",
            usage=None,
            raw_response_id=None,
        ),
        error=None,
        guardrails={},
        prompt=None,
    )
    meta = SessionMeta(
        role_title="data engineer",
        role_category="Data Engineering",
        seniority="Senior",
        interview_round="Technical Interview",
        interview_focus="Technical Knowledge",
        persona="Technical Interviewer",
    )
    session: dict = {"session_meta": meta}
    merge_message_into_session_context(
        session,
        "I migrated a legacy data warehouse to Snowflake and used dbt incremental models "
        "to reduce runtime by 40%.",
    )
    msgs = [
        ChatMessage(role="user", content="Let's start"),
        ChatMessage(role="assistant", content="First Q"),
        ChatMessage(role="user", content="Can you ask me a question related to that project?"),
    ]
    session["ia_mock_pending_question"] = "Some pending question?"
    session["ia_mock_phase"] = "awaiting_answer"
    session["ia_interview_state"] = "waiting_for_answer"

    with patch(
        "interview_app.services.chat_service.generate_questions",
        return_value=ok_question,
    ) as gen:
        out = run_turn(_settings(role_title=""), msgs, session_state=session)

    assert "Please enter a **role title**" not in out.assistant_message
    assert gen.called
    assert gen.call_args.kwargs.get("role_title") == "data engineer"
    suffix = gen.call_args.kwargs.get("mock_interview_context_suffix") or ""
    assert "snowflake" in suffix.lower() or "Snowflake" in suffix


def test_evaluation_includes_active_question_hints(input_pipeline_ok: None) -> None:
    ev = EvaluateAnswerResult(
        ok=True,
        response=LLMResponse(text="graded", model="gpt-4o-mini", usage=None, raw_response_id=None),
        error=None,
        guardrails={},
        system_prompt="sys",
        user_prompt="user",
        evaluation=EvaluationResult(
            score=7,
            criteria_met=["solid"],
            criteria_missing=["metrics"],
            critique="Add more detail.",
            improved_answer="Better.",
            follow_ups=["Next?"],
        ),
    )
    session: dict = {}
    merge_message_into_session_context(
        session,
        "I migrated a legacy data warehouse to Snowflake and used dbt incremental models.",
    )
    set_active_interview_question(
        session,
        question_text="How did you ensure data quality during the Snowflake migration?",
        question_type="contextual_follow_up",
        based_on_topics=["Snowflake", "dbt"],
        based_on_project="warehouse migration to Snowflake",
        expected_focus=["Data quality", "Migration"],
    )
    session["ia_mock_pending_question"] = (
        "How did you ensure data quality during the Snowflake migration?"
    )
    session["ia_mock_phase"] = "awaiting_answer"
    session["ia_interview_state"] = "waiting_for_answer"
    msgs = [
        ChatMessage(role="user", content="Let's start"),
        ChatMessage(role="assistant", content="Q"),
        ChatMessage(
            role="user",
            content=(
                "We used row counts and hash compares per table, plus dbt tests on uniqueness "
                "and not-null constraints before cutting traffic over."
            ),
        ),
    ]
    with patch("interview_app.services.chat_service.evaluate_answer", return_value=ev) as ev_fn:
        run_turn(_settings(), msgs, session_state=session)

    hints = (ev_fn.call_args.kwargs.get("evaluation_context_hints") or "").lower()
    assert "snowflake" in hints or "migration" in hints or "contextual" in hints


def test_clarification_does_not_wipe_context(input_pipeline_ok: None) -> None:
    session: dict = {}
    merge_message_into_session_context(session, "We used Snowflake and dbt for the migration.")
    ctx_before = get_session_interview_context(session)
    with patch("interview_app.services.chat_service.LLMClient") as mock_cls:
        mock_cls.return_value.generate_response.return_value = LLMResponse(
            text="Sure — here is clarification.",
            model="gpt-4o-mini",
            usage=None,
            raw_response_id=None,
        )
        msgs = [
            ChatMessage(role="user", content="start"),
            ChatMessage(role="assistant", content="Q"),
            ChatMessage(
                role="user",
                content="Before I answer, can you clarify if you want high-level or detailed?",
            ),
        ]
        session["ia_mock_pending_question"] = "Why eventual consistency?"
        session["ia_mock_phase"] = "awaiting_answer"
        session["ia_interview_state"] = "waiting_for_answer"
        run_turn(_settings(), msgs, session_state=session)

    ctx_after = get_session_interview_context(session)
    assert ctx_before.get("tools") == ctx_after.get("tools")


def test_multi_turn_contextual_then_answer_then_eval(input_pipeline_ok: None) -> None:
    q1 = GenerateQuestionsResult(
        ok=True,
        response=LLMResponse(
            text="1. Describe your incremental dbt strategy on Snowflake.",
            model="gpt-4o-mini",
            usage=None,
            raw_response_id=None,
        ),
        error=None,
        guardrails={},
        prompt=None,
    )
    ev = EvaluateAnswerResult(
        ok=True,
        response=LLMResponse(text="ok", model="gpt-4o-mini", usage=None, raw_response_id=None),
        error=None,
        guardrails={},
        system_prompt="s",
        user_prompt="u",
        evaluation=EvaluationResult(
            score=8,
            next_follow_up_question="How did you handle schema drift post-migration?",
        ),
    )
    session: dict = {}
    merge_message_into_session_context(
        session,
        "I migrated a legacy data warehouse to Snowflake and used dbt incremental models.",
    )
    msgs_a = [
        ChatMessage(role="user", content="Hi"),
        ChatMessage(role="assistant", content="Intro"),
        ChatMessage(role="user", content="Can you ask me a question related to that project?"),
    ]
    session["ia_mock_pending_question"] = "placeholder?"
    session["ia_mock_phase"] = "awaiting_answer"
    session["ia_interview_state"] = "waiting_for_answer"

    with patch("interview_app.services.chat_service.generate_questions", return_value=q1):
        out1 = run_turn(_settings(), msgs_a, session_state=session)
    assert (
        "incremental" in out1.assistant_message.lower() or "dbt" in out1.assistant_message.lower()
    )
    assert session.get("ia_mock_active_question", {}).get("question_type") == "contextual_follow_up"

    msgs_b = msgs_a + [
        ChatMessage(role="assistant", content=out1.assistant_message),
        ChatMessage(
            role="user",
            content=(
                "We used merge incremental models with a unique key and nightly full refreshes "
                "for dimensions; runtime dropped after clustering on the fact keys."
            ),
        ),
    ]
    with patch("interview_app.services.chat_service.evaluate_answer", return_value=ev):
        out2 = run_turn(_settings(), msgs_b, session_state=session)

    assert "Score" in out2.assistant_message or "score" in out2.assistant_message.lower()
    assert session.get("ia_mock_pending_question")
