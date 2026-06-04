"""Approximate OpenAI list pricing for UI cost estimates (USD per 1M tokens).

Values are indicative only and change on the provider side. Used only when a model
id matches a known entry; unknown models skip cost display.
"""

from __future__ import annotations

from typing import Final

# model id (lowercase) -> (input_usd_per_1m, output_usd_per_1m)
MODEL_USD_PER_1M_TOKENS: Final[dict[str, tuple[float, float]]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
}


def pricing_for_model(model_id: str | None) -> tuple[float, float] | None:
    """Return (input_usd_per_1m, output_usd_per_1m) when configured, else None."""
    if not model_id or not str(model_id).strip():
        return None
    key = str(model_id).strip().lower()
    if key in MODEL_USD_PER_1M_TOKENS:
        return MODEL_USD_PER_1M_TOKENS[key]
    for known, rates in MODEL_USD_PER_1M_TOKENS.items():
        if key.startswith(known):
            return rates
    return None
