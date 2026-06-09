from __future__ import annotations

"""Streaming behavior for mock interview conversational LLM paths."""

from unittest.mock import patch

from interview_app.app.ui_settings import UISettings
from interview_app.llm.openai_client import LLMStream
from interview_app.security.output_guard import OutputGuardResult
from interview_app.services.chat_service import (
    ChatTurnResult,
    _answer_general_question,
    _run_streamable_conversational_llm,
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


class _FakeLLMStream(LLMStream):
    def __init__(self, chunks: list[str], response: LLMResponse) -> None:
        super().__init__()
        self._fake_chunks = chunks
        self._fake_response = response

    def _produce(self):
        for chunk in self._fake_chunks:
            self._chunks.append(chunk)
            yield chunk
        self._response = self._fake_response
        self._completed = True


def test_run_streamable_conversational_llm_returns_stream_handle() -> None:
    llm_cfg = mock_llm_config_from_settings(_minimal_settings())
    fake_stream = _FakeLLMStream(["Hi", "!"], LLMResponse(text="Hi!", model="gpt-4o-mini"))

    with patch("interview_app.services.chat_service.LLMClient") as mock_cls:
        mock_cls.return_value.stream_response.return_value = fake_stream
        out = _run_streamable_conversational_llm(
            system_prompt="sys",
            user_prompt="user",
            extra_messages=None,
            llm_cfg=llm_cfg,
            temperature=0.2,
            max_tokens=100,
            llm_route="chat_conversational",
            openai_api_key=None,
            enable_streaming=True,
            llm_debug=None,
            finalize=lambda resp: ChatTurnResult(assistant_message=resp.text),
        )

    assert out.stream is not None
    assert list(out.stream) == ["Hi", "!"]
    finalized = out.stream.finalize()
    assert finalized.assistant_message == "Hi!"
    mock_cls.return_value.generate_response.assert_not_called()


def test_run_streamable_conversational_llm_falls_back_when_stream_raises() -> None:
    llm_cfg = mock_llm_config_from_settings(_minimal_settings())
    buffered = LLMResponse(text="Buffered reply.", model="gpt-4o-mini")

    with patch("interview_app.services.chat_service.LLMClient") as mock_cls:
        mock_cls.return_value.stream_response.side_effect = RuntimeError("stream unavailable")
        mock_cls.return_value.generate_response.return_value = buffered
        out = _run_streamable_conversational_llm(
            system_prompt="sys",
            user_prompt="user",
            extra_messages=None,
            llm_cfg=llm_cfg,
            temperature=0.2,
            max_tokens=100,
            llm_route="chat_conversational",
            openai_api_key=None,
            enable_streaming=True,
            llm_debug=None,
            finalize=lambda resp: ChatTurnResult(assistant_message=resp.text),
        )

    assert out.stream is None
    assert out.assistant_message == "Buffered reply."
    mock_cls.return_value.generate_response.assert_called_once()


def test_stream_finalize_runs_output_pipeline() -> None:
    resp = LLMResponse(text="system prompt: leak", model="gpt-4o-mini")
    blocked = OutputGuardResult(
        safe=False,
        text="",
        reason="The response was blocked for safety reasons. Please try again.",
        flags=["prompt_leakage_suspected"],
    )
    fake_stream = _FakeLLMStream(["bad"], resp)

    with patch("interview_app.services.chat_service.LLMClient") as mock_cls:
        mock_cls.return_value.stream_response.return_value = fake_stream
        with patch("interview_app.services.chat_service.run_output_pipeline", return_value=blocked):
            settings = _minimal_settings()
            messages = [ChatMessage(role="user", content="Hi")]
            out = _answer_general_question(
                settings,
                messages,
                "Hi",
                mock_llm_config_from_settings(settings),
                enable_streaming=True,
            )

    assert out.stream is not None
    list(out.stream)
    finalized = out.stream.finalize()
    assert finalized.assistant_message == blocked.reason


def test_answer_general_question_buffered_when_streaming_disabled() -> None:
    resp = LLMResponse(text="Hello there.", model="gpt-4o-mini")
    with patch("interview_app.services.chat_service.LLMClient") as mock_cls:
        mock_cls.return_value.generate_response.return_value = resp
        settings = _minimal_settings()
        messages = [ChatMessage(role="user", content="Hi")]
        out = _answer_general_question(
            settings,
            messages,
            "Hi",
            mock_llm_config_from_settings(settings),
            enable_streaming=False,
        )

    assert out.stream is None
    assert "hello" in out.assistant_message.lower()
    mock_cls.return_value.stream_response.assert_not_called()
