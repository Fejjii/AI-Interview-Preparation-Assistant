"""
Conversation state for the chat-based interview flow.

Initializes and updates st.session_state for:
- messages (chat history)
- current_session_id, session_meta (role, difficulty, etc.)
Helpers: get_messages, append_message, clear_messages, load_session_into_state.
"""

from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

from interview_app.app.ui_settings import UISettings
from interview_app.services.mock_interview_flow import (
    clear_mock_interview_runtime_state,
    init_mock_interview_runtime_state,
    sync_mock_interview_session_from_messages,
)
from interview_app.utils.types import ChatMessage, SessionMeta


def init_session_state() -> None:
    """Ensure required keys exist in st.session_state for chat and sessions."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "current_session_id" not in st.session_state:
        st.session_state.current_session_id = None
    if "session_meta" not in st.session_state:
        st.session_state.session_meta = None
    if "response_language" not in st.session_state:
        st.session_state.response_language = None
    if "last_scores" not in st.session_state:
        st.session_state.last_scores = []  # for adaptive difficulty
    if "ia_pending_generate" not in st.session_state:
        st.session_state.ia_pending_generate = False
    init_mock_interview_runtime_state(st.session_state)


def get_messages() -> list[ChatMessage]:
    """Return the current list of chat messages (safe copy for read)."""
    init_session_state()
    raw = st.session_state.messages
    out = []
    for m in raw:
        if isinstance(m, dict):
            out.append(
                ChatMessage(
                    role=m.get("role", "user"),
                    content=m.get("content", ""),
                    timestamp=m.get("timestamp"),
                )
            )
        elif isinstance(m, ChatMessage):
            out.append(m)
        else:
            out.append(ChatMessage(role="user", content=str(m)))
    return out


def _utc_timestamp_iso() -> str:
    """UTC ISO-8601 ending in Z (filesystem / JSON friendly)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def append_message(role: str, content: str, *, timestamp: str | None = None) -> None:
    """Append a single message to session state. Role is 'user' or 'assistant'."""
    init_session_state()
    ts = timestamp or _utc_timestamp_iso()
    st.session_state.messages.append(ChatMessage(role=role, content=content, timestamp=ts))


def clear_messages() -> None:
    """Clear chat history; keep session id and meta unless explicitly cleared elsewhere."""
    init_session_state()
    st.session_state.messages = []
    st.session_state.last_scores = []
    st.session_state.pop("ia_mock_last_llm_debug", None)
    clear_mock_interview_runtime_state(st.session_state)


def snapshot_meta_from_settings(
    settings: UISettings, session_id: str | None, title: str = ""
) -> SessionMeta:
    """Build SessionMeta from current UISettings for saving a session."""
    from datetime import datetime

    return SessionMeta(
        id=session_id or "",
        created_at=datetime.utcnow().isoformat() + "Z",
        role_category=settings.role_category,
        role_title=settings.role_title,
        seniority=settings.seniority,
        difficulty=settings.effective_question_difficulty,
        difficulty_mode=settings.question_difficulty_mode,
        interview_round=settings.interview_round,
        interview_focus=settings.interview_focus,
        interview_type=settings.interview_focus,
        persona=settings.persona,
        title=title or "Untitled session",
    )


def load_session_into_state(session_id: str, meta: SessionMeta, messages: list[dict]) -> None:
    """Load a saved session into session state so the chat re-renders."""
    init_session_state()
    st.session_state.current_session_id = session_id
    st.session_state.session_meta = meta
    loaded = [
        ChatMessage(
            role=m.get("role", "user"),
            content=m.get("content", ""),
            timestamp=m.get("timestamp"),
        )
        for m in messages
    ]
    st.session_state.messages = loaded
    sync_mock_interview_session_from_messages(st.session_state, loaded)


def messages_for_llm(messages: list[ChatMessage], last_n: int = 10) -> list[dict]:
    """Convert ChatMessage list to OpenAI-style extra_messages (last N turns)."""
    trimmed = messages[-(last_n * 2) :] if last_n else messages
    return [{"role": m.role, "content": m.content} for m in trimmed]
