from __future__ import annotations

"""Unit tests for LLM client boundary audit logging (no real API calls)."""

from unittest.mock import MagicMock, patch

import pytest

from interview_app.llm.openai_client import LLMClient
from interview_app.utils.types import LLMUsage


def _fake_completion_response(text: str = "ok") -> MagicMock:
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    usage = MagicMock()
    usage.prompt_tokens = 10
    usage.completion_tokens = 5
    usage.total_tokens = 15
    resp.usage = usage
    resp.model = "gpt-4o-mini"
    resp.id = "resp-test-1"
    return resp


def test_generate_response_logs_success_with_route(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO", logger="interview_app.llm")
    fake = _fake_completion_response()
    with patch("interview_app.llm.openai_client.OpenAI") as mock_cls:
        mock_cls.return_value.chat.completions.create.return_value = fake
        client = LLMClient(api_key="sk-test123456789012345678901234567890", model="gpt-4o-mini")
        resp = client.generate_response(
            system_prompt="sys",
            user_prompt="user",
            llm_route="unit_test_route",
            temperature=0.0,
        )
    assert resp.text == "ok"
    assert any(
        rec.message.startswith("LLM ")
        and "unit_test_route" in rec.message
        and "True" in rec.message
        for rec in caplog.records
    )


def test_generate_response_logs_failure_with_error_type(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("WARNING", logger="interview_app.llm")
    with patch("interview_app.llm.openai_client.OpenAI") as mock_cls:
        mock_cls.return_value.chat.completions.create.side_effect = RuntimeError("api down")
        client = LLMClient(api_key="sk-test123456789012345678901234567890", model="gpt-4o-mini")
        with pytest.raises(RuntimeError):
            client.generate_response(
                system_prompt="sys",
                user_prompt="user",
                llm_route="unit_fail_route",
            )
    assert any(
        rec.message.startswith("LLM ")
        and "unit_fail_route" in rec.message
        and "False" in rec.message
        and "RuntimeError" in rec.message
        for rec in caplog.records
    )


def test_log_llm_audit_includes_token_fields_when_present(caplog: pytest.LogCaptureFixture) -> None:
    from interview_app.llm.openai_client import _log_llm_audit

    caplog.set_level("INFO", logger="interview_app.llm")
    _log_llm_audit(
        llm_route="x",
        model="m",
        success=True,
        latency_ms=12.3,
        usage=LLMUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3),
    )
    assert any("prompt_tokens" in rec.message for rec in caplog.records)
