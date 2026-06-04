"""LLM client wrappers and model settings."""

from .model_settings import (
    DEFAULT_MODEL_PRESET_KEY,
    MODEL_PRESET_LABELS,
    MODEL_PRESET_SIDEBAR_OPTIONS,
    MODEL_PRESETS,
    ModelConfig,
    get_model_config,
    resolve_openai_model_id,
    sidebar_label_for_preset,
)
from .openai_client import LLMClient

__all__ = [
    "DEFAULT_MODEL_PRESET_KEY",
    "LLMClient",
    "MODEL_PRESET_LABELS",
    "MODEL_PRESET_SIDEBAR_OPTIONS",
    "MODEL_PRESETS",
    "ModelConfig",
    "get_model_config",
    "resolve_openai_model_id",
    "sidebar_label_for_preset",
]
