"""Layout helpers for saved sessions sidebar (button readability)."""

from __future__ import annotations

import re
from pathlib import Path

from interview_app.ui.theme import _build_app_css


def _session_list_source() -> str:
    controls = Path("src/interview_app/app/controls.py").read_text(encoding="utf-8")
    start = controls.index("def _render_sidebar_session_list")
    end = controls.index("def _render_sidebar_delete_all_sessions")
    return controls[start:end]


def test_saved_sessions_use_full_width_action_labels() -> None:
    source = _session_list_source()
    assert 'st.button(\n                "Open session"' in source or '"Open session"' in source
    assert '"Delete session"' in source
    assert '"Open"' not in source.replace("Open session", "")
    assert '"Delete"' not in source.replace("Delete session", "").replace("Delete all", "")


def test_saved_sessions_layout_is_vertical_not_column_actions() -> None:
    source = _session_list_source()
    assert "st.columns" not in source
    assert "st.container(border=True)" in source
    assert "ia-saved-session-card" in source


def test_saved_sessions_css_scopes_nowrap_to_session_buttons() -> None:
    css = _build_app_css(dark=False)
    assert "ia-saved-session-card" in css
    assert "white-space: nowrap" in css
    assert re.search(r"ia-saved-session-card.*stButton.*button", css, re.DOTALL)
    assert "st-key-sb_del_all_start" in css
