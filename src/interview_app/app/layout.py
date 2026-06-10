"""
Streamlit main-area layout: header, configuration summary card, primary workspace navigation.

Sidebar holds all configuration (`controls.render_sidebar_configuration`).
Main area: hero with theme toggle, Current Setup card, native ``st.tabs`` workspace nav.
"""

from __future__ import annotations

import streamlit as st

from interview_app.app.conversation_state import init_session_state
from interview_app.app.tabs.cv_prep_tab import _render_cv_interview_tab
from interview_app.app.tabs.feedback_tab import _render_answer_feedback_tab
from interview_app.app.tabs.mock_interview_tab import _render_mock_interview_tab
from interview_app.app.tabs.questions_tab import _render_question_generation_tab
from interview_app.app.ui_settings import WORKSPACE_TAB_LABELS, UISettings
from interview_app.ui.theme import render_configuration_pill_bar


def render_theme_toggle() -> None:
    """Compact light/dark control for the main header (not in sidebar)."""
    dark = st.toggle(
        "Dark mode",
        value=st.session_state.get("dark_mode", False),
        key="ia_header_dark_toggle",
        help="Switch appearance",
    )
    if dark != st.session_state.get("dark_mode", False):
        st.session_state.dark_mode = dark
        st.rerun()


def render_hero_header() -> None:
    """Page title, subtitle, and theme toggle in a compact SaaS-style header."""
    title_col, theme_col = st.columns([6, 1], gap="small", vertical_alignment="center")
    with title_col:
        st.markdown(
            """
<div class="ia-hero ia-hero-compact ia-hero-with-actions" aria-label="Application header">
  <h1 class="ia-hero-title">AI Interview Preparation Assistant</h1>
  <p class="ia-hero-subtitle">Practice realistic interviews, generate role-specific questions, and improve your answers with AI feedback.</p>
</div>
""",
            unsafe_allow_html=True,
        )
    with theme_col:
        render_theme_toggle()


def render_configuration_summary_bar(settings: UISettings) -> None:
    """Compact read-only strip of active setup (recruiter-friendly)."""
    st.markdown(
        render_configuration_pill_bar(settings=settings),
        unsafe_allow_html=True,
    )


def render_main_content(settings: UISettings) -> None:
    """Workspace: summary bar + native tabs + tab panels."""
    init_session_state()

    render_configuration_summary_bar(settings)

    tab_labels = list(WORKSPACE_TAB_LABELS)
    if "ia_workspace_tab" not in st.session_state:
        st.session_state.ia_workspace_tab = tab_labels[0]
    if st.session_state.ia_workspace_tab not in tab_labels:
        st.session_state.ia_workspace_tab = tab_labels[0]

    st.markdown(
        '<div class="ia-workspace-nav-label">Workspace</div>',
        unsafe_allow_html=True,
    )
    active_tab = str(st.session_state.ia_workspace_tab)
    tab_panels = st.tabs(tab_labels, default=active_tab)

    with tab_panels[0]:
        _render_mock_interview_tab(settings)
    with tab_panels[1]:
        _render_question_generation_tab(settings)
    with tab_panels[2]:
        _render_cv_interview_tab(settings)
    with tab_panels[3]:
        _render_answer_feedback_tab(settings)
