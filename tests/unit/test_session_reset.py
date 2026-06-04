"""Full workspace reset and ephemeral-work detection."""

from __future__ import annotations

from interview_app.app import cv_session_state as cvs
from interview_app.app.session_reset import reset_all_workspace_state, session_has_ephemeral_work
from interview_app.app.usage_mode import (
    KEY_BYO_KEY_HINT,
    KEY_BYO_OPENAI_API_KEY,
    KEY_USAGE_MODE,
    UsageMode,
)


def test_session_has_ephemeral_work_messages() -> None:
    ss: dict = {"messages": [{"role": "user", "content": "hi"}]}
    assert session_has_ephemeral_work(ss) is True


def test_session_has_ephemeral_work_cv_ready() -> None:
    ss: dict = {cvs.KEY_ANALYSIS_READY: True}
    assert session_has_ephemeral_work(ss) is True


def test_session_has_ephemeral_work_compare_pair() -> None:
    ss: dict = {"ia_compare_pair": {"a_key": "x"}}
    assert session_has_ephemeral_work(ss) is True


def test_reset_clears_chat_cv_compare_and_byo_keys() -> None:
    ss: dict = {
        "messages": [1],
        "current_session_id": "sid",
        "session_meta": {},
        "ia_compare_pair": {"x": 1},
        "ia_mock_pending_question": "Old question?",
        "ia_mock_phase": "awaiting_answer",
        KEY_USAGE_MODE: UsageMode.BYO.value,
        KEY_BYO_OPENAI_API_KEY: "sk-12345678901234567890123456789012",
        KEY_BYO_KEY_HINT: "sk-...9012",
        cvs.KEY_ANALYSIS_READY: True,
        cvs.KEY_VERSION: 2,
    }
    reset_all_workspace_state(ss)
    assert ss.get("messages") == []
    assert ss.get("current_session_id") is None
    assert ss.get("ia_compare_pair") is None
    assert ss.get("ia_mock_pending_question") is None
    assert ss.get("ia_mock_phase") == "not_started"
    assert cvs.analysis_ready(ss) is False
    assert KEY_USAGE_MODE not in ss
    assert KEY_BYO_OPENAI_API_KEY not in ss


def test_reset_clears_feedback_widget_keys() -> None:
    ss: dict = {
        "messages": [],
        "ia_feedback_question": "q",
        "ia_feedback_answer": "a",
        cvs.KEY_VERSION: 0,
    }
    reset_all_workspace_state(ss)
    assert "ia_feedback_question" not in ss
    assert "ia_feedback_answer" not in ss
