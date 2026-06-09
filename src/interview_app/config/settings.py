"""Centralized configuration (settings) for the app.

This project uses environment variables as the primary configuration mechanism.
For local development, a `.env` file in the project root is supported.

Typical flow:
- `streamlit_app.py` loads `.env` so env vars are available
- `LLMClient` calls `get_settings()` to read OPENAI_API_KEY, defaults, etc.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class SecuritySettings(BaseSettings):
    """Configurable thresholds and toggles for the security / guardrail layer."""

    model_config = SettingsConfigDict(env_prefix="SECURITY_", extra="ignore")

    max_input_length: int = Field(
        default=8000,
        description="Maximum allowed characters for a single user input.",
    )
    rate_limit_max_requests: int = Field(
        default=20,
        description="Max LLM requests allowed per rate-limit window.",
    )
    rate_limit_window_seconds: int = Field(
        default=60,
        description="Rate-limit sliding window in seconds.",
    )
    moderation_enabled: bool = Field(
        default=True,
        description="Enable lightweight content moderation.",
    )
    output_max_length: int = Field(
        default=16000,
        description="Maximum characters for model output before truncation.",
    )
    prompt_injection_strict: bool = Field(
        default=False,
        description="When True, use stricter (more false-positives) injection detection.",
    )
    prompt_injection_classifier_enabled: bool = Field(
        default=False,
        description=(
            "Reserved for a future optional LLM-based injection classifier. "
            "When False (default), only heuristic detection runs."
        ),
    )
    cv_max_file_bytes: int = Field(
        default=5 * 1024 * 1024,
        description="Maximum upload size for CV files (PDF/DOCX).",
    )
    cv_max_text_chars: int = Field(
        default=20_000,
        description="Maximum characters of extracted CV text sent through guardrails and to the LLM.",
    )


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and an optional `.env` file.

    Notes:
    - `.env` is optional; environment variables always take precedence.
    - Keep secrets out of source control; use `.env.example` as documentation.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = Field(default="dev", description="Application environment (dev/prod/test).")

    show_diagnostics: bool = Field(
        default=False,
        description=(
            "Show Developer diagnostics in the sidebar. Only applies when APP_ENV=dev; "
            "ignored in prod/test deployments."
        ),
    )

    openai_api_key: SecretStr | None = Field(
        default=None,
        description="OpenAI API key. Prefer setting via environment variable OPENAI_API_KEY.",
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        description=(
            "Default model when LLMClient is built without an explicit model: preset key "
            "(gpt-4.1, gpt-4.1-mini, gpt-4.1-nano, gpt-4o, gpt-4o-mini) or raw API model id."
        ),
    )
    openai_temperature: float = Field(
        default=0.2, ge=0.0, le=2.0, description="Default sampling temperature."
    )
    openai_max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description=(
            "Max retries for transient OpenAI API failures (429, 5xx, timeouts). "
            "Uses the OpenAI SDK built-in exponential backoff with jitter."
        ),
    )
    sessions_dir: str = Field(
        default="data/sessions",
        description="Directory for lightweight session JSON files (relative to cwd or absolute).",
    )
    enable_streaming: bool = Field(
        default=True,
        description=(
            "When True, Mock Interview conversational assistant replies stream progressively. "
            "Structured JSON flows (questions, CV, evaluation) always use buffered mode."
        ),
    )
    demo_max_llm_calls_per_session: int = Field(
        default=10,
        ge=1,
        le=10_000,
        description=(
            "Maximum OpenAI API calls per browser session in Demo access mode. "
            "BYO key mode is not limited by this setting."
        ),
    )

    security: SecuritySettings = Field(default_factory=SecuritySettings)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Load and cache settings (singleton-style).

    Streamlit re-runs the script frequently; caching avoids repeated env parsing and
    keeps config access fast and consistent during a session.
    """
    return Settings()


def get_security_settings() -> SecuritySettings:
    """Shortcut to access the security sub-config."""
    return get_settings().security


def show_sidebar_diagnostics() -> bool:
    """
    Whether the sidebar Developer diagnostics panel should render.

    Public-safe default: hidden unless ``APP_ENV=dev`` and ``SHOW_DIAGNOSTICS=true``.
    """
    settings = get_settings()
    if settings.app_env.strip().lower() != "dev":
        return False
    return settings.show_diagnostics
