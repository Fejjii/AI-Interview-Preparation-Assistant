"""Mock Interview voice answer input (record/upload → transcribe → review → send)."""

from __future__ import annotations

from typing import Any

import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

from interview_app.app.tabs.shared import session_openai_key
from interview_app.services.transcription_service import transcribe_audio

KEY_VOICE_TRANSCRIPT = "ia_voice_transcript_draft"
KEY_VOICE_STATUS = "ia_voice_status_message"
KEY_VOICE_ERROR = "ia_voice_last_error"

_VOICE_UPLOAD_TYPES = ("wav", "mp3", "m4a", "webm", "mpeg", "mp4", "ogg")


def clear_voice_input_state(session_state: dict[str, Any]) -> None:
    """Drop ephemeral voice UI state (no audio bytes are stored here)."""
    for key in (KEY_VOICE_TRANSCRIPT, KEY_VOICE_STATUS, KEY_VOICE_ERROR):
        session_state.pop(key, None)


def _read_uploaded_audio(upload: UploadedFile | None) -> tuple[bytes, str] | None:
    if upload is None:
        return None
    data = upload.getvalue()
    if not data:
        return None
    return data, upload.name or "recording.webm"


def render_voice_input_panel() -> str | None:
    """
    Render the collapsed voice input expander for Mock Interview.

    Returns transcript text when the user clicks **Send transcript**; otherwise ``None``.
    Audio is never written to session storage — only the optional text draft key is used.
    """
    with st.expander("Voice input", expanded=False):
        st.caption(
            "Record or upload a short answer. Audio is sent to your configured AI provider "
            "for transcription only; it is not stored after processing."
        )

        recorded = st.audio_input(
            "Record or upload answer",
            key="ia_voice_audio_input",
        )
        uploaded = st.file_uploader(
            "Or upload an audio file",
            type=list(_VOICE_UPLOAD_TYPES),
            key="ia_voice_file_upload",
            label_visibility="collapsed",
        )

        status = st.session_state.get(KEY_VOICE_STATUS)
        if isinstance(status, str) and status.strip():
            st.info(status)

        err = st.session_state.get(KEY_VOICE_ERROR)
        if isinstance(err, str) and err.strip():
            st.error(err)

        transcribe_clicked = st.button(
            "Transcribe",
            key="ia_voice_transcribe_btn",
            type="secondary",
            use_container_width=True,
        )
        if transcribe_clicked:
            source = _read_uploaded_audio(uploaded) or _read_uploaded_audio(recorded)
            if source is None:
                st.session_state[KEY_VOICE_ERROR] = "Record or upload audio before transcribing."
                st.session_state[KEY_VOICE_STATUS] = ""
            else:
                audio_bytes, filename = source
                with st.spinner("Transcribing…"):
                    result = transcribe_audio(
                        audio_bytes,
                        filename=filename,
                        openai_api_key=session_openai_key(),
                        session_state=dict(st.session_state),
                    )
                if result.ok:
                    st.session_state[KEY_VOICE_TRANSCRIPT] = result.transcript
                    st.session_state[KEY_VOICE_ERROR] = ""
                    latency = (
                        f"{result.latency_ms:.0f} ms" if result.latency_ms is not None else "—"
                    )
                    st.session_state[KEY_VOICE_STATUS] = (
                        f"Transcription complete ({result.provider}, {result.model}, {latency}). "
                        "Review and edit below, then send when ready."
                    )
                else:
                    st.session_state[KEY_VOICE_ERROR] = result.error or "Transcription failed."
                    st.session_state[KEY_VOICE_STATUS] = ""
            st.rerun()

        if KEY_VOICE_TRANSCRIPT not in st.session_state:
            st.session_state[KEY_VOICE_TRANSCRIPT] = ""

        st.text_area(
            "Review transcript",
            key=KEY_VOICE_TRANSCRIPT,
            height=120,
            placeholder="Transcribed text will appear here for review and editing.",
        )
        transcript = str(st.session_state.get(KEY_VOICE_TRANSCRIPT) or "")

        send_clicked = st.button(
            "Send transcript",
            key="ia_voice_send_btn",
            type="primary",
            use_container_width=True,
            disabled=not transcript.strip(),
        )
        if send_clicked and transcript.strip():
            clear_voice_input_state(dict(st.session_state))
            return transcript.strip()

    return None
