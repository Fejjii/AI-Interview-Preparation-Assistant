from __future__ import annotations

"""Unit tests for OpenAI client retry configuration (no live API calls)."""

from unittest.mock import MagicMock, patch

import pytest
from openai import APIConnectionError, APIStatusError, RateLimitError

from interview_app.config.settings import Settings
from interview_app.llm.openai_client import LLMClient, is_retryable_openai_error


def test_openai_client_passes_max_retries_from_settings() -> None:
    settings = Settings(_env_file=None, openai_max_retries=5)
    with patch("interview_app.llm.openai_client.OpenAI") as mock_cls:
        LLMClient(settings=settings, api_key="sk-test123456789012345678901234567890")
    mock_cls.assert_called_once()
    assert mock_cls.call_args.kwargs["max_retries"] == 5


def test_openai_max_retries_default_is_three() -> None:
    settings = Settings(_env_file=None)
    assert settings.openai_max_retries == 3


def test_openai_max_retries_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_MAX_RETRIES", "0")
    from interview_app.config.settings import get_settings

    get_settings.cache_clear()
    try:
        assert get_settings().openai_max_retries == 0
    finally:
        get_settings.cache_clear()


def test_is_retryable_openai_error_rate_limit() -> None:
    err = RateLimitError(
        "rate limited",
        response=MagicMock(status_code=429, headers={}),
        body=None,
    )
    assert is_retryable_openai_error(err) is True


def test_is_retryable_openai_error_503() -> None:
    err = APIStatusError(
        "unavailable",
        response=MagicMock(status_code=503, headers={}),
        body=None,
    )
    assert is_retryable_openai_error(err) is True


def test_is_retryable_openai_error_401() -> None:
    err = APIStatusError(
        "unauthorized",
        response=MagicMock(status_code=401, headers={}),
        body=None,
    )
    assert is_retryable_openai_error(err) is False


def test_is_retryable_openai_error_connection() -> None:
    assert is_retryable_openai_error(APIConnectionError(request=MagicMock())) is True


def test_is_retryable_openai_error_non_openai() -> None:
    assert is_retryable_openai_error(RuntimeError("other")) is False
