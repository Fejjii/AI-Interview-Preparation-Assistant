from __future__ import annotations

"""Tests for chat LLM path security (protect_system_prompt, output pipeline, llm_route)."""

from unittest.mock import patch

from interview_app.app.ui_settings import UISettings
from interview_app.security.output_guard import OutputGuardResult
from interview_app.services.chat_service import (
    _answer_general_question,
    mock_llm_config_from_settings,
)
from interview_app.utils.types import ChatMessage, LLMResponse


def _minimal_settings() -> UISettings:
    return UISettings(
        role_category="Other",
        role_title="Engineer",
        seniority="Mid-Level",
        interview_round="Technical Interview",
        interview_focus="Behavioral / Soft Skills",
        job_description="",
        persona="Hiring Manager",
        question_difficulty_mode="auto",
        effective_question_difficulty="Medium",
        prompt_strategy="zero_shot",
        model_preset="gpt-4o-mini",
        temperature=0.2,
        top_p=1.0,
        max_tokens=800,
        show_debug=False,
        response_language="en",
        usage_mode="demo",
        byo_key_hint=None,
    )


def test_answer_general_question_uses_protect_system_prompt_and_output_pipeline() -> None:
    """Conversational chat LLM calls must use hardened system prompt and output guard."""
    resp = LLMResponse(
        text="I'm doing well, thanks!", model="gpt-4o-mini", usage=None, raw_response_id=None
    )
    with patch("interview_app.services.chat_service.LLMClient") as mock_cls:
        mock_cls.return_value.generate_response.return_value = resp
        settings = _minimal_settings()
        messages = [ChatMessage(role="user", content="How are you?")]
        out = _answer_general_question(
            settings, messages, "How are you?", mock_llm_config_from_settings(settings)
        )

    assert "thanks" in out.assistant_message.lower() or "well" in out.assistant_message.lower()
    mock_cls.assert_called_once()
    assert mock_cls.call_args.kwargs.get("api_key") is None
    kwargs = mock_cls.return_value.generate_response.call_args.kwargs
    assert kwargs["llm_route"] == "chat_conversational"
    assert "Security:" in kwargs["system_prompt"]
    assert "Never reveal" in kwargs["system_prompt"]


def test_answer_general_question_output_guard_failure_message() -> None:
    """When output guard blocks, user sees a safe reason string."""
    resp = LLMResponse(
        text="system prompt: leak", model="gpt-4o-mini", usage=None, raw_response_id=None
    )
    blocked = OutputGuardResult(
        safe=False,
        text="",
        reason="The response was blocked for safety reasons. Please try again.",
        flags=["prompt_leakage_suspected"],
    )
    with patch("interview_app.services.chat_service.LLMClient") as mock_cls:
        mock_cls.return_value.generate_response.return_value = resp
        with patch("interview_app.services.chat_service.run_output_pipeline", return_value=blocked):
            settings = _minimal_settings()
            messages = [ChatMessage(role="user", content="Hi")]
            out = _answer_general_question(
                settings, messages, "Hi", mock_llm_config_from_settings(settings)
            )

    assert out.assistant_message == blocked.reason


def test_answer_general_question_passes_byo_api_key_to_client() -> None:
    """BYO session key is forwarded to LLMClient and never appears in assistant output."""
    resp = LLMResponse(text="Hello.", model="gpt-4o-mini", usage=None, raw_response_id=None)
    with patch("interview_app.services.chat_service.LLMClient") as mock_cls:
        mock_cls.return_value.generate_response.return_value = resp
        settings = _minimal_settings()
        messages = [ChatMessage(role="user", content="Hi")]
        secret = "sk-test123456789012345678901234567890"
        out = _answer_general_question(
            settings,
            messages,
            "Hi",
            mock_llm_config_from_settings(settings),
            openai_api_key=secret,
        )

    assert "sk-" not in out.assistant_message
    assert mock_cls.call_args.kwargs.get("api_key") == secret
