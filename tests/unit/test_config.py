from __future__ import annotations

"""
Unit tests for configuration loading (`interview_app.config.settings`).

These tests ensure:
- defaults are sensible when no `.env` is present
- environment variables override defaults
- the cached `get_settings()` can be reset between tests
"""

from interview_app.config.settings import Settings, get_settings, show_sidebar_diagnostics


def test_settings_defaults() -> None:
    """Settings() should produce stable defaults without requiring env vars."""
    # Ensure this unit test is deterministic even when a local `.env` exists.
    settings = Settings(_env_file=None)
    assert settings.app_env == "dev"
    assert settings.openai_api_key is None
    assert settings.openai_model
    assert settings.openai_temperature == 0.2
    assert settings.openai_max_retries == 3
    assert settings.show_diagnostics is False


def test_show_sidebar_diagnostics_requires_dev_and_flag(monkeypatch) -> None:
    """Developer diagnostics are opt-in and never shown outside APP_ENV=dev."""
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("SHOW_DIAGNOSTICS", "true")
    get_settings.cache_clear()
    assert show_sidebar_diagnostics() is False

    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("SHOW_DIAGNOSTICS", "false")
    get_settings.cache_clear()
    assert show_sidebar_diagnostics() is False

    monkeypatch.setenv("SHOW_DIAGNOSTICS", "true")
    get_settings.cache_clear()
    assert show_sidebar_diagnostics() is True


def test_settings_env_overrides(monkeypatch) -> None:
    """Environment variables should override defaults (and `.env`)."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("OPENAI_TEMPERATURE", "0.7")
    monkeypatch.setenv("OPENAI_MAX_RETRIES", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.app_env == "test"
    assert settings.openai_model == "gpt-4o-mini"
    assert settings.openai_temperature == 0.7
    assert settings.openai_max_retries == 1
    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == "test-key"
