"""Recruiter-facing demo UI structure tests (source-level, no Streamlit runtime)."""

from __future__ import annotations

from pathlib import Path

from interview_app.app.ui_settings import WORKSPACE_TAB_LABELS, UISettings
from interview_app.ui import presentation
from interview_app.ui.theme import render_configuration_pill_bar


def _read(rel: str) -> str:
    return Path(rel).read_text(encoding="utf-8")


def test_presentation_flags_hide_advanced_chrome() -> None:
    assert presentation.show_advanced_sidebar_controls() is False
    assert presentation.show_technical_metadata() is False
    assert presentation.show_strategy_comparison_by_default() is False
    assert presentation.allow_debug_prompts() is False


def test_sanitize_recruiter_demo_session_state_clears_debug_flag() -> None:
    state: dict[str, object] = {"ia_show_debug": True, "messages": []}
    presentation.sanitize_recruiter_demo_session_state(state)
    assert "ia_show_debug" not in state
    assert state["messages"] == []


def test_sidebar_does_not_render_prompt_strategy_or_generation() -> None:
    source = _read("src/interview_app/app/controls.py")
    assert '"Prompt strategy"' not in source
    assert '"Generation"' not in source
    assert '"Model"' not in source
    assert '"Show debug prompts"' not in source
    assert '"Temperature"' not in source
    assert '"Top-p"' not in source
    assert '"Max tokens"' not in source
    assert "Developer notes" not in source
    assert "render_sidebar_deployment_content" not in source


def test_sidebar_workspace_shortcuts_removed() -> None:
    source = _read("src/interview_app/app/controls.py")
    for label in (
        "sb_btn_generate",
        "sb_btn_cv",
        "sb_btn_mock",
        "sb_btn_reset",
        "Workspace shortcuts",
    ):
        assert label not in source


def test_saved_sessions_remain_in_sidebar() -> None:
    source = _read("src/interview_app/app/controls.py")
    assert "Saved sessions" in source
    assert "_render_sidebar_session_list" in source
    assert "Open session" in source


def test_dark_mode_toggle_in_main_header() -> None:
    source = _read("src/interview_app/app/layout.py")
    assert "render_theme_toggle" in source
    assert "ia_header_dark_toggle" in source
    assert "dark_mode_toggle" not in source


def test_sidebar_branding_present() -> None:
    source = _read("src/interview_app/app/controls.py")
    assert "AI Interview Coach" in source
    assert "Interview profile" in source
    assert "Getting started" in _read("src/interview_app/ui/usage_mode_panel.py")


def test_core_workspace_tabs_defined() -> None:
    assert WORKSPACE_TAB_LABELS == (
        "Mock Interview",
        "Interview Questions",
        "CV Interview Prep",
        "Feedback / Evaluation",
    )
    layout_source = _read("src/interview_app/app/layout.py")
    for label in WORKSPACE_TAB_LABELS:
        assert label in layout_source or "_render_" in layout_source


def test_configuration_pill_bar_shows_role_context_only() -> None:
    settings = UISettings(
        role_category="Software Engineering",
        role_title="Backend Engineer",
        seniority="Mid-Level",
        interview_round="Technical Interview",
        interview_focus="System design",
        job_description="",
        persona="Hiring Manager",
        question_difficulty_mode="Auto",
        effective_question_difficulty="Medium",
        prompt_strategy="zero_shot",
        model_preset="gpt-4o-mini",
        temperature=0.2,
        top_p=1.0,
        max_tokens=800,
        show_debug=False,
        response_language="en",
        usage_mode="demo",
        byo_key_hint=None,
    )
    html = render_configuration_pill_bar(settings=settings)
    assert "Backend Engineer" in html
    assert "Mid-Level" in html
    assert "Technical Interview" in html
    assert "Demo access" not in html
    assert "Temperature" not in html
    assert "Technical settings" not in html


def test_questions_tab_hides_strategy_caption_by_default() -> None:
    source = _read("src/interview_app/app/tabs/questions_tab.py")
    assert "Active prompt strategy" not in source
    assert "Advanced: compare prompting approaches" in source


def test_mock_interview_export_under_more_actions() -> None:
    source = _read("src/interview_app/app/tabs/mock_interview_tab.py")
    assert "More actions" in source
    assert "mock_interview_export_download" in source
    assert "Usage details" not in source


def test_voice_panel_still_wired_in_mock_interview_tab() -> None:
    source = _read("src/interview_app/app/tabs/mock_interview_tab.py")
    assert "render_voice_input_panel" in source


def test_controls_forces_show_debug_false() -> None:
    source = _read("src/interview_app/app/controls.py")
    assert "show_debug = False" in source
    assert "sanitize_recruiter_demo_session_state" in source


def test_display_hides_technical_metadata_and_debug_prompts() -> None:
    source = _read("src/interview_app/ui/display.py")
    assert "show_technical_metadata" in source
    assert "allow_debug_prompts" in source
