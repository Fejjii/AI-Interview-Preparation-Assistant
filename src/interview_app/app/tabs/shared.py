"""Helpers shared across workspace tab panels."""

from __future__ import annotations

import html

import streamlit as st

from interview_app.app.usage_mode import openai_api_key_for_llm


def render_section_heading(title: str, subtitle: str) -> None:
    """Primary section title + muted subtext (workspace panels)."""
    safe_t = html.escape(title)
    safe_s = html.escape(subtitle)
    st.markdown(
        f'<div class="ia-section-head"><h2 class="ia-section-title">{safe_t}</h2>'
        f'<p class="ia-section-sub">{safe_s}</p></div>',
        unsafe_allow_html=True,
    )


def session_openai_key() -> str | None:
    """Explicit BYO key for this Streamlit session, or None for Demo (server env key)."""
    return openai_api_key_for_llm(dict(st.session_state))
