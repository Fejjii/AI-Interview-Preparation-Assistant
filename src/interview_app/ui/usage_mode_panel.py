"""Sidebar: Session setup / Usage mode (Demo vs Bring Your Own OpenAI key)."""

from __future__ import annotations

import html
from typing import Any

import streamlit as st

from interview_app.app.session_reset import reset_all_workspace_state, session_has_ephemeral_work
from interview_app.app.usage_mode import (
    KEY_BYO_KEY_HINT,
    KEY_BYO_OPENAI_API_KEY,
    KEY_USAGE_MODE,
    UsageMode,
    demo_mode_backend_key_configured,
    demo_remaining_calls,
    get_demo_max_llm_calls,
    get_demo_usage_count,
    key_tail_from_masked_hint,
    mask_api_key_for_display,
    validate_openai_api_key_format,
)
from interview_app.security.redaction import redact_secrets

_MODE_LABELS: tuple[str, str] = ("Demo access", "Use my own OpenAI key")


def _sidebar_usage_title(title: str, hint: str | None = None) -> None:
    st.sidebar.markdown(
        f'<p class="ia-sidebar-section">{html.escape(title)}</p>',
        unsafe_allow_html=True,
    )
    if hint:
        st.sidebar.caption(hint)


def _render_applied_status(applied: str, hint: object) -> None:
    """Minimal read-only status for the currently applied usage mode."""
    sb = st.sidebar
    if applied == UsageMode.DEMO.value:
        sb.markdown(
            '<div class="ia-usage-status-card ia-usage-status-demo" role="status">'
            '<div class="ia-usage-status-title">Demo access active</div>'
            '<div class="ia-usage-status-sub">Shared demo credentials for this session.</div>'
            "</div>",
            unsafe_allow_html=True,
        )
        remaining = demo_remaining_calls(st.session_state)
        if remaining is not None:
            used = get_demo_usage_count(st.session_state)
            cap = get_demo_max_llm_calls()
            sb.caption(f"Demo calls: {used}/{cap} used ({remaining} remaining this session).")
        return

    tail = key_tail_from_masked_hint(str(hint)) if hint else None
    meta = ""
    if tail:
        meta = f'<div class="ia-usage-status-meta">Key ending in {html.escape(tail)}</div>'
    sb.markdown(
        '<div class="ia-usage-status-card ia-usage-status-byo" role="status">'
        '<div class="ia-usage-status-title">Personal API key active</div>'
        '<div class="ia-usage-status-sub">Used only for this session. '
        "Not stored permanently.</div>"
        f"{meta}"
        "</div>",
        unsafe_allow_html=True,
    )


_BYO_LABELS = frozenset({"Use my own OpenAI key", "Use your own OpenAI API key"})


def render_usage_mode_setup() -> None:
    """
    Configuration block for Demo vs BYO. Apply performs a full workspace reset
    and re-binds API credentials for this Streamlit session only.
    """
    sb = st.sidebar
    _sidebar_usage_title(
        "Getting started",
        "Demo access or your own OpenAI API key for this session.",
    )

    sb.radio(
        "Access",
        options=list(_MODE_LABELS),
        key="um_draft_radio",
        help="Demo access uses the app owner's configured key. Your own key is session-only.",
        label_visibility="collapsed",
    )

    draft_label = str(st.session_state.get("um_draft_radio") or _MODE_LABELS[0])
    byo_selected = draft_label in _BYO_LABELS

    if byo_selected:
        show = sb.checkbox("Show key", value=False, key="ia_byo_show_key")
        inp_type = "default" if show else "password"
        sb.text_input(
            "OpenAI API key",
            value="",
            placeholder="sk-...",
            type=inp_type,
            key="ia_byo_key_input",
            help="Used only for this session. Not persisted to disk or browser storage.",
        )

    applied = str(st.session_state.get(KEY_USAGE_MODE) or UsageMode.DEMO.value)
    hint = st.session_state.get(KEY_BYO_KEY_HINT)
    _render_applied_status(applied, hint)

    if applied == UsageMode.DEMO.value and not demo_mode_backend_key_configured():
        sb.info("Demo access is enabled when the app owner has configured an API key.")

    has_work = session_has_ephemeral_work(st.session_state)
    if has_work:
        sb.checkbox(
            "I understand this will clear the mock interview, CV prep, questions, and feedback inputs.",
            key="ia_usage_ack_reset",
        )

    if sb.button("Apply", use_container_width=True, type="primary", key="um_apply_btn"):
        choice = str(st.session_state.get("um_draft_radio") or _MODE_LABELS[0])
        want_byo = choice in _BYO_LABELS
        next_mode = UsageMode.BYO if want_byo else UsageMode.DEMO

        if session_has_ephemeral_work(st.session_state) and not st.session_state.get(
            "ia_usage_ack_reset"
        ):
            sb.error("Confirm the checkbox above to discard current workspace data.")
        elif want_byo:
            raw = st.session_state.get("ia_byo_key_input")
            secret = (raw or "").strip() if isinstance(raw, str) else ""
            ok_fmt, err = validate_openai_api_key_format(secret)
            if not ok_fmt:
                sb.error(redact_secrets(err))
            else:
                _finalize_apply(st.session_state, next_mode, choice, secret, want_byo)
        else:
            _finalize_apply(st.session_state, next_mode, choice, "", want_byo)


def _finalize_apply(
    session_state: dict[str, Any],
    next_mode: UsageMode,
    choice_label: str,
    secret: str,
    want_byo: bool,
) -> None:
    reset_all_workspace_state(session_state)
    session_state[KEY_USAGE_MODE] = next_mode.value
    if want_byo:
        session_state[KEY_BYO_OPENAI_API_KEY] = secret
        session_state[KEY_BYO_KEY_HINT] = mask_api_key_for_display(secret)
    session_state.pop("ia_byo_key_input", None)
    session_state["um_draft_radio"] = choice_label
    session_state.pop("ia_usage_ack_reset", None)

    if next_mode == UsageMode.DEMO:
        st.toast("Started a new session with demo access.")
    else:
        st.toast("Started a new session using your API key.")

    st.rerun()
