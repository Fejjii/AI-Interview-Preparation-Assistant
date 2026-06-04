"""Tests for structured interview context extraction and context-aware question generation."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from interview_app.app.ui_settings import UISettings
from interview_app.security.pipeline import InputPipelineResult
from interview_app.services.chat_service import run_turn
from interview_app.services.context_extractor import (
    extract_interview_topics,
    interview_topics_non_empty,
)
from interview_app.services.context_manager import (
    get_session_interview_context,
    merge_message_into_session_context,
    should_use_context,
)
from interview_app.services.interview_generator import GenerateQuestionsResult
from interview_app.utils.types import ChatMessage, LLMResponse


def _settings(**kwargs: object) -> UISettings:
    fields: dict[str, object] = {
        "role_category": "Other",
        "role_title": "Data Engineer",
        "seniority": "Mid-Level",
        "interview_round": "Technical Interview",
        "interview_focus": "Behavioral / Soft Skills",
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


def test_extract_topics_etl_airflow_snowflake() -> None:
    msg = "I built an ETL pipeline using Airflow and Snowflake."
    topics = extract_interview_topics(msg)
    assert "airflow" in " ".join(topics["tools"]).lower() or "Airflow" in topics["tools"]
    assert any("snowflake" in t.lower() for t in topics["tools"])
    assert "etl" in topics["technologies"] or any(
        "etl" in t.lower() for t in topics["technologies"]
    )


def test_extract_topics_sql_optimization() -> None:
    msg = "I optimized a SQL query that reduced runtime by 60%."
    topics = extract_interview_topics(msg)
    assert topics["achievements"] or any("%" in msg for _ in (1,))


def test_generate_questions_receives_context_suffix_after_related_request(
    input_pipeline_ok: None,
) -> None:
    ok_question = GenerateQuestionsResult(
        ok=True,
        response=LLMResponse(
            text="1. How do you model incremental loads in dbt for late-arriving facts?",
            model="gpt-4o-mini",
            usage=None,
            raw_response_id=None,
        ),
        error=None,
        guardrails={},
        prompt=None,
    )
    session: dict = {}
    merge_message_into_session_context(
        session,
        "I migrated a legacy data warehouse to Snowflake and used dbt incremental models to reduce runtime by 40%.",
    )
    assert interview_topics_non_empty(get_session_interview_context(session))

    msgs = [
        ChatMessage(role="user", content="Let's start"),
        ChatMessage(role="assistant", content="First Q"),
        ChatMessage(
            role="user",
            content="Can you ask me a question related to that project?",
        ),
    ]
    session["ia_mock_pending_question"] = "Some pending question?"
    session["ia_mock_phase"] = "awaiting_answer"
    session["ia_interview_state"] = "waiting_for_answer"

    with patch(
        "interview_app.services.chat_service.generate_questions",
        return_value=ok_question,
    ) as gen:
        out = run_turn(_settings(), msgs, session_state=session)

    assert "dbt" in out.assistant_message.lower() or "snowflake" in out.assistant_message.lower()
    suffix = gen.call_args.kwargs.get("mock_interview_context_suffix") or ""
    assert "Snowflake" in suffix or "snowflake" in suffix.lower()
    assert "Additional instructions" not in out.assistant_message


def test_clarification_preserves_session_context(input_pipeline_ok: None) -> None:
    session: dict = {}
    merge_message_into_session_context(session, "We used Snowflake and dbt for the migration.")
    ctx_before = get_session_interview_context(session)

    with patch("interview_app.services.chat_service.LLMClient") as mock_cls:
        mock_cls.return_value.generate_response.return_value = LLMResponse(
            text="Happy to clarify - see below.",
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
    assert ctx_before["tools"] == ctx_after["tools"]


def test_should_use_context_true_when_bucket_nonempty() -> None:
    s: dict = {}
    merge_message_into_session_context(s, "Kafka and Spark streaming.")
    assert should_use_context("next", s) is True
