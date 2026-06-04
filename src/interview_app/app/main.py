"""Streamlit composition root for the interview app.

Wires together theme injection, session initialization, sidebar controls (which
produce ``UISettings``), and the main workspace from ``layout``. This module is
the orchestration layer between ``streamlit_app`` (entry) and feature UI in
``layout`` / ``controls``.

Side effects: mutates Streamlit session state and renders the full page.
"""

from __future__ import annotations

import streamlit as st

from interview_app.app.controls import render_sidebar_configuration
from interview_app.app.conversation_state import init_session_state
from interview_app.app.layout import (
    render_hero_header,
    render_main_content,
)
from interview_app.app.usage_mode import init_usage_mode_defaults
from interview_app.ui.theme import inject_theme


def _init_dark_mode() -> None:
    """Ensure dark_mode key exists in session state."""
    if "dark_mode" not in st.session_state:
        st.session_state.dark_mode = False


def run() -> None:
    """Build and render the Streamlit page."""
    st.set_page_config(
        page_title="AI Interview Preparation Assistant",
        page_icon="\U0001f3af",
        layout="wide",
    )
    _init_dark_mode()
    inject_theme()
    init_session_state()
    init_usage_mode_defaults(st.session_state)

    settings = render_sidebar_configuration()
    render_hero_header()
    render_main_content(settings)
