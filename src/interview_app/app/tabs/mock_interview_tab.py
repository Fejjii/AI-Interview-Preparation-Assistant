"""Mock Interview workspace tab."""

import json
import logging

import streamlit as st

from interview_app.app.conversation_state import (
    append_message,
    clear_messages,
    get_messages,
    snapshot_meta_from_settings,
)
from interview_app.app.tabs.shared import render_section_heading, session_openai_key
from interview_app.app.ui_settings import UISettings
from interview_app.config.settings import get_settings
from interview_app.services.chat_service import LlmTurnDebug, run_turn as chat_run_turn
from interview_app.storage.sessions import save_session
from interview_app.ui.display import show_error, show_prompt_debug, show_settings_debug
from interview_app.utils.errors import safe_user_message
from interview_app.utils.language import detect_language
from interview_app.utils.mock_interview_export import (
    build_mock_interview_export_payload,
    mock_interview_export_filename,
)


def _render_session_row_compact(settings: UISettings) -> None:
    """Session status, name, save, new chat, export — compact card above chat."""
    messages = get_messages()
    session_id = st.session_state.get("current_session_id")
    status = "Saved" if session_id else ("In progress" if messages else "New session")
    can_save = bool(messages)

    with st.container(border=True):
        st.markdown(
            '<p class="ia-session-card-header">Session</p>',
            unsafe_allow_html=True,
        )
        c0, c1, c2, c3, c4 = st.columns([1.15, 2.4, 0.85, 0.9, 1.0], gap="small")
        with c0:
            st.markdown(
                f'<p class="ia-session-status">{status}</p>',
                unsafe_allow_html=True,
            )
        with c1:
            st.text_input(
                "Session name",
                placeholder="e.g. Backend practice",
                key="session_title",
                label_visibility="collapsed",
            )
        with c2:
            if st.button(
                "Save",
                use_container_width=True,
                type="primary",
                key="main_save_session",
                disabled=not can_save,
            ):
                if not messages:
                    st.warning("No messages to save yet.")
                else:
                    session_title = str(st.session_state.get("session_title") or "")
                    meta = snapshot_meta_from_settings(
                        settings,
                        session_id,
                        title=session_title or "Untitled session",
                    )
                    msgs = [m.model_dump(exclude_none=True) for m in messages]
                    sid = save_session(
                        session_id,
                        meta,
                        msgs,
                        title=session_title or "Untitled session",
                        session_state=dict(st.session_state),
                    )
                    st.session_state.current_session_id = sid
                    st.toast(f'Saved as "{session_title or "Untitled"}"')
                    st.rerun()
        with c3:
            if st.button(
                "New chat",
                use_container_width=True,
                key="main_new_session",
                type="secondary",
            ):
                clear_messages()
                st.session_state.current_session_id = None
                st.session_state.session_meta = None
                st.rerun()
        with c4:
            export_payload = build_mock_interview_export_payload(
                settings=settings,
                messages=messages,
                session_title=str(st.session_state.get("session_title") or ""),
            )
            st.download_button(
                label="Export JSON",
                data=json.dumps(export_payload, indent=2, ensure_ascii=False),
                file_name=mock_interview_export_filename(
                    str(st.session_state.get("session_title") or "")
                ),
                mime="application/json",
                key="mock_interview_export_download",
                help="Download this mock interview as structured JSON (metadata + messages).",
                use_container_width=True,
                disabled=not messages,
            )


_logger = logging.getLogger(__name__)


def _run_mock_turn_with_optional_stream(
    settings: UISettings,
    messages: list,
) -> tuple[str, str | None, LlmTurnDebug | None]:
    """Run one mock interview turn; stream conversational replies when enabled."""
    enable_stream = get_settings().enable_streaming
    try:
        with st.spinner("Thinking…"):
            result = chat_run_turn(
                settings,
                messages,
                session_state=st.session_state,
                openai_api_key=session_openai_key(),
                enable_streaming=enable_stream,
            )
    except Exception as exc:
        msg = safe_user_message(exc)
        return f"Sorry, {msg}", None, None

    if result.stream is not None:
        buffer: list[str] = []
        try:
            with st.chat_message("assistant"):
                placeholder = st.empty()
                for chunk in result.stream:
                    buffer.append(chunk)
                    placeholder.markdown("".join(buffer))
                finalized = result.stream.finalize()
                placeholder.markdown(finalized.assistant_message)
            return (
                finalized.assistant_message,
                finalized.usage_summary,
                finalized.llm_debug,
            )
        except Exception:
            _logger.debug("Mock interview stream failed; retrying buffered mode.", exc_info=True)
            fallback = chat_run_turn(
                settings,
                messages,
                session_state=st.session_state,
                openai_api_key=session_openai_key(),
                enable_streaming=False,
            )
            with st.chat_message("assistant"):
                st.markdown(fallback.assistant_message)
            return (
                fallback.assistant_message,
                fallback.usage_summary,
                fallback.llm_debug,
            )

    return result.assistant_message, result.usage_summary, result.llm_debug


def _render_mock_interview_tab(settings: UISettings) -> None:
    """Primary workspace: session row + wide chat."""
    render_section_heading(
        "Mock Interview",
        "Answer as you would live. The interviewer uses your sidebar configuration and adapts each turn.",
    )

    with st.expander("How to use", expanded=False):
        st.markdown(
            '<p class="ia-instruction-hint">Say hello or that you’re ready to begin — the interviewer '
            "opens with a short structure line and the <strong>first question</strong> immediately. "
            "After each substantive answer you get structured feedback and a follow-up. "
            "Adjust role and round in the sidebar anytime.</p>",
            unsafe_allow_html=True,
        )

    _render_session_row_compact(settings)

    messages = get_messages()
    with st.container(border=True):
        if not messages:
            st.info(
                "Say hello or that you’re ready — the mock interviewer will start with one structure sentence "
                "and then your **first question** (no need to ask for it explicitly)."
            )
        else:
            for msg in messages:
                with st.chat_message(msg.role):
                    st.markdown(msg.content)

    if prompt := st.chat_input("Type your answer or message…"):
        if st.session_state.get("response_language") is None and prompt.strip():
            st.session_state.response_language = detect_language(prompt)
        append_message("user", prompt)
        try:
            updated = get_messages()
            assistant_message, usage_summary, llm_debug = _run_mock_turn_with_optional_stream(
                settings,
                updated,
            )
            append_message("assistant", assistant_message)
            if usage_summary:
                st.session_state["ia_mock_last_usage"] = usage_summary
            if llm_debug is not None:
                st.session_state["ia_mock_last_llm_debug"] = {
                    "system_prompt": llm_debug.system_prompt,
                    "user_prompt": llm_debug.user_prompt,
                    "model": llm_debug.model,
                    "temperature": llm_debug.temperature,
                    "top_p": llm_debug.top_p,
                    "max_tokens": llm_debug.max_tokens,
                }
        except Exception as exc:
            msg = safe_user_message(exc)
            append_message("assistant", f"Sorry, {msg}")
            show_error(title="Chat error", body=msg)
        st.rerun()

    usage = st.session_state.get("ia_mock_last_usage")
    if usage:
        with st.expander("Usage details", expanded=False):
            st.caption(str(usage))

    if settings.show_debug:
        dbg = st.session_state.get("ia_mock_last_llm_debug")
        if isinstance(dbg, dict) and dbg.get("system_prompt") and dbg.get("user_prompt"):
            top_p = dbg.get("top_p")
            top_p_s = f"{float(top_p):.2f}" if top_p is not None else "default"
            with st.expander("Last mock interview LLM call (debug)", expanded=False):
                st.caption(
                    f"Model **{dbg.get('model', '')}** · temperature={dbg.get('temperature')} · "
                    f"top_p={top_p_s} · max_tokens={dbg.get('max_tokens')}"
                )
                show_prompt_debug(
                    system_prompt=str(dbg["system_prompt"]),
                    user_prompt=str(dbg["user_prompt"]),
                )
        show_settings_debug(settings=settings, extra={"message_count": len(messages)})
