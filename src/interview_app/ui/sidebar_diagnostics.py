"""Sidebar developer diagnostics: non-secret runtime configuration for local debugging."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from interview_app.app.ui_settings import UISettings
from interview_app.app.usage_mode import UsageMode
from interview_app.config.settings import (
    get_security_settings,
    get_settings,
    show_sidebar_diagnostics,
)
from interview_app.llm.model_settings import MODEL_PRESET_LABELS, resolve_openai_model_id


def _sessions_dir_display() -> str:
    """Prefer a short relative path over a resolved absolute path."""
    raw = get_settings().sessions_dir.strip() or "data/sessions"
    path = Path(raw)
    if not path.is_absolute():
        return raw
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return path.name or raw


def _server_openai_key_configured() -> bool:
    key = get_settings().openai_api_key
    if key is None:
        return False
    secret = key.get_secret_value()
    return bool(secret and secret.strip())


def render_sidebar_diagnostics(settings: UISettings) -> None:
    """
    Collapsed-by-default developer panel (no network calls, no secret values).

    Only rendered when ``show_sidebar_diagnostics()`` is True (dev + SHOW_DIAGNOSTICS).
    """
    if not show_sidebar_diagnostics():
        return

    sb = st.sidebar
    with sb.expander("Developer diagnostics", expanded=False):
        app_settings = get_settings()
        security = get_security_settings()
        preset = settings.model_preset
        preset_label = MODEL_PRESET_LABELS.get(preset, preset)  # type: ignore[arg-type]
        resolved_model = resolve_openai_model_id(preset)

        usage = settings.usage_mode
        if usage == UsageMode.BYO.value:
            mode_line = "Personal API key"
            if settings.byo_key_hint:
                mode_line += f" — hint: {settings.byo_key_hint}"
        else:
            mode_line = "Demo access"

        rows: list[tuple[str, str]] = [
            ("App environment", app_settings.app_env),
            ("Model preset", f"{preset_label} (`{resolved_model}`)"),
            ("Access mode", mode_line),
            (
                "Server API key",
                "Configured" if _server_openai_key_configured() else "Not configured",
            ),
            ("Sessions directory", _sessions_dir_display()),
            ("Moderation enabled", "Yes" if security.moderation_enabled else "No"),
            (
                "Strict prompt injection",
                "Yes" if security.prompt_injection_strict else "No",
            ),
            (
                "Injection classifier (reserved)",
                "Enabled" if security.prompt_injection_classifier_enabled else "Disabled",
            ),
            ("OpenAI max retries", str(app_settings.openai_max_retries)),
        ]

        for label, value in rows:
            st.markdown(f"**{label}:** {value}")

        st.caption(
            "Local only. Evaluations: `pytest tests/evaluations -v` or "
            "`python evaluations/run_evaluations.py`"
        )

    sb.divider()
