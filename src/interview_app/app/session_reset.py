"""Full workspace reset when usage mode or BYO key changes.

Clears Streamlit session data for mock interview, CV prep, question generation,
feedback inputs, rate limits, and cached comparisons — without touching stable
sidebar preferences (role, appearance). Saved mock sessions on disk remain, but
they are **scoped** by usage mode / BYO key (see ``storage.sessions``); the UI only
lists sessions for the active scope.
"""

from __future__ import annotations

from typing import Any

from interview_app.app import cv_session_state as cvs
from interview_app.app.usage_mode import (
    KEY_BYO_KEY_HINT,
    KEY_BYO_OPENAI_API_KEY,
    KEY_DEMO_LLM_CALL_COUNT,
    KEY_USAGE_DRAFT_RADIO,
    KEY_USAGE_MODE,
)
from interview_app.security.rate_limiter import reset_rate_limit
from interview_app.services.mock_interview_flow import clear_mock_interview_runtime_state
from interview_app.ui.voice_input import clear_voice_input_state

# Widget/session keys to drop so Streamlit remounts fresh inputs (feedback, CV form, etc.).
_WORKSPACE_WIDGET_KEYS: tuple[str, ...] = (
    "session_title",
    "ia_n_questions",
    "ia_compare_sel_a",
    "ia_compare_sel_b",
    "ia_feedback_question",
    "ia_feedback_answer",
    "cv_target_role_input",
    "cv_interview_type",
    "cv_difficulty",
    "cv_n_questions",
    "cv_target_company",
    "cv_extra_job_context",
    "ia_usage_ack_reset",
    "ia_byo_key_input",
    "ia_byo_show_key",
    KEY_USAGE_DRAFT_RADIO,
)


def _pop_cv_practice_answer_keys(session_state: dict[str, Any]) -> None:
    """Remove dynamic practice-answer widget keys (cv_pa_<ver>_<i>)."""
    for k in list(session_state.keys()):
        if isinstance(k, str) and k.startswith("cv_pa_"):
            session_state.pop(k, None)


def session_has_ephemeral_work(session_state: dict[str, Any]) -> bool:
    """
    True when switching mode would discard user-visible work (confirmation gate).

    Does not treat empty mock sessions as work.
    """
    if session_state.get("messages"):
        return True
    if session_state.get("current_session_id"):
        return True
    if cvs.analysis_ready(session_state):
        return True
    pair = session_state.get("ia_compare_pair")
    if isinstance(pair, dict) and pair:
        return True
    return False


def reset_all_workspace_state(session_state: dict[str, Any]) -> None:
    """
    Clear transcripts, CV workspace, comparisons, feedback fields, rate limits,
    and in-memory BYO key material. Caller should set new usage mode / key after.

    Preserves sidebar role/interview configuration and dark mode.
    """
    session_state.setdefault("messages", [])
    session_state["messages"] = []
    session_state.setdefault("last_scores", [])
    session_state["last_scores"] = []
    session_state["current_session_id"] = None
    session_state["session_meta"] = None
    clear_mock_interview_runtime_state(session_state)
    clear_voice_input_state(session_state)
    session_state["response_language"] = None
    session_state["ia_pending_generate"] = False
    session_state.pop("ia_compare_pair", None)

    cvs.clear_cv_workspace(session_state)

    reset_rate_limit(session_state)
    session_state.pop(KEY_DEMO_LLM_CALL_COUNT, None)

    for k in _WORKSPACE_WIDGET_KEYS:
        session_state.pop(k, None)

    _pop_cv_practice_answer_keys(session_state)

    # Default workspace tab: Mock Interview
    from interview_app.app.ui_settings import WORKSPACE_TAB_LABELS

    session_state["ia_workspace_tab"] = WORKSPACE_TAB_LABELS[0]

    # Clear BYO secrets so a new mode/key pair must be applied explicitly.
    session_state.pop(KEY_BYO_OPENAI_API_KEY, None)
    session_state.pop(KEY_BYO_KEY_HINT, None)
    session_state.pop(KEY_USAGE_MODE, None)
