"""Named OpenAI model presets (temperature, top_p, max_tokens defaults).

Sidebar preset keys map to ``ModelConfig`` rows. ``LLMClient`` resolves preset keys to
the OpenAI ``model`` parameter via ``resolve_openai_model_id`` so UI, settings, and
the API stay aligned.

Inputs: string keys from UI; outputs: ``ModelConfig`` for client construction.
"""

from __future__ import annotations

from typing import Literal, TypeGuard

from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    """Configuration defaults for a given model preset."""

    name: str = Field(description="OpenAI API model id (same as preset key for supported models).")
    default_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    default_top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    default_max_tokens: int | None = Field(default=800, ge=1)


# Preset keys are the exact OpenAI model ids used in API calls.
ModelPresetKey = Literal[
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "gpt-4o",
    "gpt-4o-mini",
]

DEFAULT_MODEL_PRESET_KEY: ModelPresetKey = "gpt-4o-mini"

MODEL_PRESET_LABELS: dict[ModelPresetKey, str] = {
    "gpt-4.1": "GPT-4.1",
    "gpt-4.1-mini": "GPT-4.1 mini",
    "gpt-4.1-nano": "GPT-4.1 nano",
    "gpt-4o": "GPT-4o",
    "gpt-4o-mini": "GPT-4o mini",
}

# Sidebar order: display label, preset key (OpenAI model id).
MODEL_PRESET_SIDEBAR_OPTIONS: tuple[tuple[str, ModelPresetKey], ...] = (
    ("GPT-4.1", "gpt-4.1"),
    ("GPT-4.1 mini", "gpt-4.1-mini"),
    ("GPT-4.1 nano", "gpt-4.1-nano"),
    ("GPT-4o", "gpt-4o"),
    ("GPT-4o mini", "gpt-4o-mini"),
)

MODEL_PRESETS: dict[ModelPresetKey, ModelConfig] = {
    "gpt-4.1": ModelConfig(name="gpt-4.1", default_temperature=0.2, default_max_tokens=1400),
    "gpt-4.1-mini": ModelConfig(
        name="gpt-4.1-mini", default_temperature=0.2, default_max_tokens=1200
    ),
    "gpt-4.1-nano": ModelConfig(
        name="gpt-4.1-nano", default_temperature=0.2, default_max_tokens=1000
    ),
    "gpt-4o": ModelConfig(name="gpt-4o", default_temperature=0.2, default_max_tokens=1200),
    "gpt-4o-mini": ModelConfig(
        name="gpt-4o-mini", default_temperature=0.2, default_max_tokens=1000
    ),
}


def is_model_preset_key(key: str) -> TypeGuard[ModelPresetKey]:
    """Return True if `key` is one of the known `MODEL_PRESETS` keys."""
    return key in MODEL_PRESETS


def resolve_openai_model_id(key: str) -> str:
    """Map a preset key to its OpenAI model id; pass through unknown strings (e.g. env overrides)."""
    if is_model_preset_key(key):
        return MODEL_PRESETS[key].name
    return key


def sidebar_label_for_preset(key: str) -> str:
    """Human-readable sidebar / summary label for a preset key."""
    if is_model_preset_key(key):
        return MODEL_PRESET_LABELS[key]
    return key


def get_model_config(key: str) -> ModelConfig:
    """
    Get a model preset by key.

    Raises:
        KeyError: if the key is not a known preset.
    """

    return MODEL_PRESETS[key]  # type: ignore[index]
