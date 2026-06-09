"""Layout helpers for saved sessions sidebar (button readability)."""

from __future__ import annotations

from pathlib import Path

from interview_app.ui.theme import _build_app_css


def test_saved_sessions_css_prevents_button_wrap() -> None:
    css = _build_app_css(dark=False)
    assert "ia-saved-session-row" in css
    assert "white-space: nowrap" in css
    assert "st-key-sb_del_all_start" in css


def test_saved_sessions_row_uses_compact_action_labels() -> None:
    source = Path("src/interview_app/app/controls.py").read_text(encoding="utf-8")
    assert 'st.button("Open"' in source
    assert 'st.button(\n                "Delete"' in source or 'st.button("Delete"' in source
    assert "ia-saved-session-row" in source
    assert "_render_sidebar_session_list" in source
