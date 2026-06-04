from __future__ import annotations

from interview_app.utils.types import LLMResponse, LLMUsage
from interview_app.utils.usage_formatting import (
    estimate_cost_usd,
    format_usage_summary,
    format_usage_summary_from_parts,
)


def test_format_usage_summary_tokens_and_latency() -> None:
    resp = LLMResponse(
        text="ok",
        model="gpt-4o-mini",
        usage=LLMUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        latency_ms=1234.56,
        provider="openai",
    )
    summary = format_usage_summary(resp)
    assert summary is not None
    assert "gpt-4o-mini" in summary
    assert "in 100" in summary
    assert "out 50" in summary
    assert "1,234 ms" in summary or "1235 ms" in summary


def test_format_usage_summary_includes_estimate_for_known_model() -> None:
    resp = LLMResponse(
        model="gpt-4o-mini",
        usage=LLMUsage(prompt_tokens=1_000_000, completion_tokens=0, total_tokens=1_000_000),
    )
    summary = format_usage_summary(resp)
    assert summary is not None
    assert "Est. cost" in summary
    assert "approximate" in summary.lower()


def test_format_usage_summary_no_cost_for_unknown_model() -> None:
    resp = LLMResponse(
        model="unknown-model-xyz",
        usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        latency_ms=100.0,
    )
    summary = format_usage_summary(resp)
    assert summary is not None
    assert "Est. cost" not in (summary or "")


def test_format_usage_summary_empty_returns_none() -> None:
    assert format_usage_summary(LLMResponse()) is None


def test_estimate_cost_usd_none_without_usage() -> None:
    assert estimate_cost_usd(model="gpt-4o-mini", usage=None) is None


def test_format_usage_summary_from_parts() -> None:
    summary = format_usage_summary_from_parts(
        model="gpt-4o",
        usage=LLMUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        latency_ms=50.0,
    )
    assert summary is not None
    assert "gpt-4o" in summary
