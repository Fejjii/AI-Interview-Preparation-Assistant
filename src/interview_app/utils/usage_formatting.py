"""Format LLM usage metadata for compact Streamlit captions."""

from __future__ import annotations

from interview_app.utils.model_pricing import pricing_for_model
from interview_app.utils.types import LLMResponse, LLMUsage


def estimate_cost_usd(
    *,
    model: str | None,
    usage: LLMUsage | None,
) -> float | None:
    """
    Rough USD estimate from token counts and ``model_pricing`` table.

    Returns None when pricing is unknown or token counts are missing.
    """
    if usage is None:
        return None
    rates = pricing_for_model(model)
    if rates is None:
        return None
    in_rate, out_rate = rates
    prompt = usage.prompt_tokens
    completion = usage.completion_tokens
    if prompt is None and completion is None:
        return None
    cost = 0.0
    if prompt is not None:
        cost += (prompt / 1_000_000.0) * in_rate
    if completion is not None:
        cost += (completion / 1_000_000.0) * out_rate
    return cost if cost > 0 else None


def format_usage_summary(response: LLMResponse) -> str | None:
    """
    One-line usage summary for UI captions.

    Includes model, tokens, latency, and an estimated cost only when pricing exists.
    """
    usage = response.usage
    has_tokens = usage is not None and any(
        v is not None for v in (usage.prompt_tokens, usage.completion_tokens, usage.total_tokens)
    )
    has_latency = response.latency_ms is not None
    has_model = bool(response.model)
    if not (has_model or has_tokens or has_latency):
        return None

    parts: list[str] = []
    if response.model:
        parts.append(f"Model: {response.model}")
    if response.provider and has_model:
        parts.append(f"Provider: {response.provider}")

    if usage is not None:
        token_bits: list[str] = []
        if usage.prompt_tokens is not None:
            token_bits.append(f"in {usage.prompt_tokens:,}")
        if usage.completion_tokens is not None:
            token_bits.append(f"out {usage.completion_tokens:,}")
        if usage.total_tokens is not None:
            token_bits.append(f"total {usage.total_tokens:,}")
        if token_bits:
            parts.append("Tokens: " + ", ".join(token_bits))

    if response.latency_ms is not None:
        parts.append(f"Latency: {response.latency_ms:.0f} ms")

    est = estimate_cost_usd(model=response.model, usage=usage)
    if est is not None:
        parts.append(f"Est. cost: ~${est:.4f} (approximate)")

    if not parts:
        return None
    return " · ".join(parts)


def format_usage_summary_from_parts(
    *,
    model: str | None = None,
    provider: str | None = "openai",
    usage: LLMUsage | None = None,
    latency_ms: float | None = None,
) -> str | None:
    """Build a usage summary without a full ``LLMResponse`` instance."""
    return format_usage_summary(
        LLMResponse(
            model=model,
            provider=provider,
            usage=usage,
            latency_ms=latency_ms,
        )
    )
