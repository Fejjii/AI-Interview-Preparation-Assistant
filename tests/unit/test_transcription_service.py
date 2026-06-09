"""Unit tests for OpenAI voice transcription (Mock Interview)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from interview_app.app.usage_mode import (
    DEMO_LIMIT_MESSAGE,
    KEY_DEMO_LLM_CALL_COUNT,
    KEY_USAGE_MODE,
    UsageMode,
    get_demo_usage_count,
)
from interview_app.config.settings import Settings, get_settings
from interview_app.services.transcription_service import transcribe_audio


def _demo_session(count: int = 0) -> dict[str, object]:
    return {KEY_USAGE_MODE: UsageMode.DEMO.value, KEY_DEMO_LLM_CALL_COUNT: count}


def _byo_session(count: int = 0) -> dict[str, object]:
    return {KEY_USAGE_MODE: UsageMode.BYO.value, KEY_DEMO_LLM_CALL_COUNT: count}


def _settings(**kwargs: object) -> Settings:
    return Settings(_env_file=None, **kwargs)


def test_transcription_uses_byo_key_when_provided() -> None:
    ss = _byo_session()
    with patch("interview_app.services.transcription_service.OpenAI") as mock_cls:
        mock_cls.return_value.audio.transcriptions.create.return_value = "Hello from mic."
        result = transcribe_audio(
            b"fake-audio",
            filename="answer.webm",
            openai_api_key="sk-12345678901234567890123456789012",
            session_state=ss,
            settings=_settings(openai_api_key=None),
        )

    assert result.ok is True
    assert result.transcript == "Hello from mic."
    mock_cls.assert_called_once()
    call_kwargs = mock_cls.call_args.kwargs
    assert call_kwargs["api_key"] == "sk-12345678901234567890123456789012"
    assert "sk-" not in str(result)


def test_transcription_uses_server_key_in_demo_mode() -> None:
    ss = _demo_session()
    with patch("interview_app.services.transcription_service.OpenAI") as mock_cls:
        mock_cls.return_value.audio.transcriptions.create.return_value = "Demo transcript."
        result = transcribe_audio(
            b"fake-audio",
            openai_api_key=None,
            session_state=ss,
            settings=_settings(openai_api_key="sk-serverkey123456789012345678901"),
        )

    assert result.ok is True
    mock_cls.assert_called_once_with(
        api_key="sk-serverkey123456789012345678901",
        max_retries=3,
    )


def test_demo_limit_blocks_transcription(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_MAX_LLM_CALLS_PER_SESSION", "1")
    get_settings.cache_clear()

    ss = _demo_session(1)
    with patch("interview_app.services.transcription_service.OpenAI") as mock_cls:
        result = transcribe_audio(
            b"fake-audio",
            openai_api_key=None,
            session_state=ss,
            settings=_settings(openai_api_key="sk-serverkey123456789012345678901"),
        )

    assert result.ok is False
    assert result.error == DEMO_LIMIT_MESSAGE
    mock_cls.assert_not_called()
    get_settings.cache_clear()


def test_successful_transcription_increments_demo_counter() -> None:
    ss = _demo_session(0)
    with patch("interview_app.services.transcription_service.OpenAI") as mock_cls:
        mock_cls.return_value.audio.transcriptions.create.return_value = "Answer text."
        result = transcribe_audio(
            b"fake-audio",
            openai_api_key=None,
            session_state=ss,
            settings=_settings(openai_api_key="sk-serverkey123456789012345678901"),
        )

    assert result.ok is True
    assert get_demo_usage_count(ss) == 1


def test_byo_transcription_does_not_increment_demo_counter() -> None:
    ss = _byo_session(0)
    with patch("interview_app.services.transcription_service.OpenAI") as mock_cls:
        mock_cls.return_value.audio.transcriptions.create.return_value = "BYO answer."
        result = transcribe_audio(
            b"fake-audio",
            openai_api_key="sk-12345678901234567890123456789012",
            session_state=ss,
            settings=_settings(openai_api_key="sk-serverkey123456789012345678901"),
        )

    assert result.ok is True
    assert get_demo_usage_count(ss) == 0


def test_provider_errors_return_safe_messages() -> None:
    ss = _demo_session()
    with patch("interview_app.services.transcription_service.OpenAI") as mock_cls:
        mock_cls.return_value.audio.transcriptions.create.side_effect = RuntimeError("api down")
        with patch(
            "interview_app.services.transcription_service.safe_user_message",
            return_value="The AI service is temporarily unavailable.",
        ):
            result = transcribe_audio(
                b"fake-audio",
                openai_api_key="sk-12345678901234567890123456789012",
                session_state=ss,
                settings=_settings(openai_api_key="sk-serverkey123456789012345678901"),
            )

    assert result.ok is False
    assert result.error == "The AI service is temporarily unavailable."
    assert "sk-" not in (result.error or "")


def test_oversized_audio_rejected_without_api_call() -> None:
    ss = _demo_session()
    tiny_limit = _settings(security={"voice_max_audio_bytes": 10})
    with patch("interview_app.services.transcription_service.OpenAI") as mock_cls:
        result = transcribe_audio(
            b"x" * 20,
            session_state=ss,
            settings=tiny_limit,
            openai_api_key="sk-12345678901234567890123456789012",
        )

    assert result.ok is False
    assert "too large" in (result.error or "").lower()
    mock_cls.assert_not_called()
