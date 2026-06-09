from __future__ import annotations

"""Unit tests for LLMClient.stream_response (mocked OpenAI stream; no real API)."""

from unittest.mock import MagicMock, patch

import pytest

from interview_app.llm.openai_client import LLMClient
from interview_app.utils.types import LLMUsage


def _stream_events(chunks: list[str], *, with_usage: bool = True) -> list[MagicMock]:
    events: list[MagicMock] = []
    for piece in chunks:
        delta = MagicMock()
        delta.content = piece
        choice = MagicMock()
        choice.delta = delta
        event = MagicMock()
        event.choices = [choice]
        event.id = "stream-test-1"
        event.model = "gpt-4o-mini"
        event.usage = None
        events.append(event)
    if with_usage:
        usage_event = MagicMock()
        usage_event.choices = []
        usage_event.id = "stream-test-1"
        usage_event.model = "gpt-4o-mini"
        usage = MagicMock()
        usage.prompt_tokens = 12
        usage.completion_tokens = 6
        usage.total_tokens = 18
        usage_event.usage = usage
        events.append(usage_event)
    return events


def test_stream_response_aggregates_text_and_usage(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO", logger="interview_app.llm")
    events = _stream_events(["Hello", ", ", "world"])
    with patch("interview_app.llm.openai_client.OpenAI") as mock_cls:
        mock_cls.return_value.chat.completions.create.return_value = iter(events)
        client = LLMClient(api_key="sk-test123456789012345678901234567890", model="gpt-4o-mini")
        stream = client.stream_response(
            system_prompt="sys",
            user_prompt="user",
            llm_route="unit_stream_route",
        )
        collected = list(stream)

    assert collected == ["Hello", ", ", "world"]
    resp = stream.response
    assert resp.text == "Hello, world"
    assert resp.model == "gpt-4o-mini"
    assert resp.usage == LLMUsage(prompt_tokens=12, completion_tokens=6, total_tokens=18)
    assert resp.latency_ms is not None
    assert resp.raw_response_id == "stream-test-1"
    assert any("unit_stream_route" in rec.message for rec in caplog.records)


def test_stream_response_without_usage_still_returns_latency() -> None:
    events = _stream_events(["Done."], with_usage=False)
    with patch("interview_app.llm.openai_client.OpenAI") as mock_cls:
        mock_cls.return_value.chat.completions.create.return_value = iter(events)
        client = LLMClient(api_key="sk-test123456789012345678901234567890", model="gpt-4o-mini")
        stream = client.stream_response(system_prompt="sys", user_prompt="user")
        assert list(stream) == ["Done."]

    resp = stream.response
    assert resp.text == "Done."
    assert resp.usage is None
    assert resp.latency_ms is not None


def test_stream_response_logs_failure_and_raises(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("WARNING", logger="interview_app.llm")
    with patch("interview_app.llm.openai_client.OpenAI") as mock_cls:
        mock_cls.return_value.chat.completions.create.side_effect = RuntimeError("stream down")
        client = LLMClient(api_key="sk-test123456789012345678901234567890", model="gpt-4o-mini")
        stream = client.stream_response(
            system_prompt="sys",
            user_prompt="user",
            llm_route="unit_stream_fail",
        )
        with pytest.raises(RuntimeError, match="stream down"):
            list(stream)

    assert any(
        "unit_stream_fail" in rec.message and "False" in rec.message for rec in caplog.records
    )
    with pytest.raises(RuntimeError, match="stream down"):
        _ = stream.response


def test_stream_response_passes_stream_options_and_preserves_params() -> None:
    with patch("interview_app.llm.openai_client.OpenAI") as mock_cls:
        mock_cls.return_value.chat.completions.create.return_value = iter(
            _stream_events(["x"], with_usage=False)
        )
        client = LLMClient(
            api_key="sk-test123456789012345678901234567890",
            model="gpt-4o-mini",
            temperature=0.4,
            top_p=0.9,
            max_tokens=256,
        )
        list(
            client.stream_response(
                system_prompt="sys",
                user_prompt="user",
                temperature=0.1,
                top_p=0.8,
                max_tokens=128,
                extra_messages=[{"role": "assistant", "content": "prior"}],
            )
        )
        kwargs = mock_cls.return_value.chat.completions.create.call_args.kwargs
        assert kwargs["stream"] is True
        assert kwargs["stream_options"] == {"include_usage": True}
        assert kwargs["temperature"] == 0.1
        assert kwargs["top_p"] == 0.8
        assert kwargs["max_tokens"] == 128
        assert kwargs["messages"][1]["content"] == "prior"
