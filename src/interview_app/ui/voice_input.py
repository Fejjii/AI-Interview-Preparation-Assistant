"""Mock Interview voice answer input (record/upload → transcribe → review → send)."""

from __future__ import annotations

from typing import Any, Literal

import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

from interview_app.app.tabs.shared import session_openai_key
from interview_app.services.transcription_service import MSG_NO_AUDIO, transcribe_audio

KEY_VOICE_TRANSCRIPT = "ia_voice_transcript_draft"
KEY_VOICE_STATUS = "ia_voice_status_message"
KEY_VOICE_HINT = "ia_voice_hint_message"
KEY_VOICE_PHASE = "ia_voice_phase"

# Legacy key — cleared on reset for older sessions.
KEY_VOICE_ERROR = "ia_voice_last_error"

_VOICE_UPLOAD_TYPES = ("wav", "mp3", "m4a", "webm", "mpeg", "mp4", "ogg")
VoicePhase = Literal["ready", "transcribed"]

MSG_MIC_TIP = (
    "If your browser blocks the microphone, use **Upload audio instead** "
    "(works on Streamlit Cloud)."
)


def clear_voice_input_state(session_state: dict[str, Any]) -> None:
    """Drop ephemeral voice UI state (no audio bytes are stored here)."""
    for key in (
        KEY_VOICE_TRANSCRIPT,
        KEY_VOICE_STATUS,
        KEY_VOICE_HINT,
        KEY_VOICE_PHASE,
        KEY_VOICE_ERROR,
    ):
        session_state.pop(key, None)
    for widget_key in (
        "ia_voice_audio_input",
        "ia_voice_file_upload",
        "ia_voice_transcribe_btn",
        "ia_voice_send_btn",
        "ia_voice_clear_btn",
    ):
        session_state.pop(widget_key, None)


def clear_voice_transcript_draft(session_state: dict[str, Any]) -> None:
    """Clear review text and hints without resetting the whole voice panel."""
    session_state[KEY_VOICE_TRANSCRIPT] = ""
    session_state[KEY_VOICE_STATUS] = voice_status_line(
        "ready", has_audio=False, has_transcript=False
    )
    session_state[KEY_VOICE_PHASE] = "ready"
    session_state.pop(KEY_VOICE_HINT, None)
    session_state.pop(KEY_VOICE_ERROR, None)


def _read_uploaded_audio(upload: UploadedFile | None) -> tuple[bytes, str] | None:
    if upload is None:
        return None
    data = upload.getvalue()
    if not data:
        return None
    return data, upload.name or "recording.webm"


def resolve_voice_audio_source(
    recorded: UploadedFile | None,
    uploaded: UploadedFile | None,
) -> tuple[bytes, str] | None:
    """Prefer a fresh recording; fall back to an uploaded file."""
    return _read_uploaded_audio(recorded) or _read_uploaded_audio(uploaded)


def has_voice_audio_ready(
    recorded: UploadedFile | None,
    uploaded: UploadedFile | None,
) -> bool:
    return resolve_voice_audio_source(recorded, uploaded) is not None


def voice_status_line(
    phase: VoicePhase,
    *,
    has_audio: bool,
    has_transcript: bool,
    transcribing: bool = False,
) -> str:
    if transcribing:
        return "Transcribing…"
    if phase == "transcribed" or has_transcript:
        return "Transcript ready"
    if has_audio:
        return "Recording or audio selected"
    return "Ready"


def render_voice_hint_html(message: str, *, tone: str = "info") -> str:
    safe = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<p class="ia-voice-hint ia-voice-hint-{tone}">{safe}</p>'


def _voice_phase_and_transcript() -> tuple[str, bool, VoicePhase]:
    if KEY_VOICE_TRANSCRIPT not in st.session_state:
        st.session_state[KEY_VOICE_TRANSCRIPT] = ""
    transcript = str(st.session_state.get(KEY_VOICE_TRANSCRIPT) or "")
    has_transcript = bool(transcript.strip())
    phase_raw = str(st.session_state.get(KEY_VOICE_PHASE) or "ready")
    if phase_raw not in ("ready", "transcribed"):
        phase: VoicePhase = "transcribed" if has_transcript else "ready"
    else:
        phase = phase_raw  # type: ignore[assignment]
    return transcript, has_transcript, phase


def _render_voice_status_and_transcribe(
    recorded: UploadedFile | None,
    uploaded: UploadedFile | None,
    *,
    audio_ready: bool,
    has_transcript: bool,
    phase: VoicePhase,
) -> None:
    status_line = str(st.session_state.get(KEY_VOICE_STATUS) or "").strip()
    if not status_line:
        status_line = voice_status_line(
            "transcribed" if has_transcript else phase,
            has_audio=audio_ready,
            has_transcript=has_transcript,
        )
    st.markdown(
        f'<p class="ia-voice-status">{status_line}</p>',
        unsafe_allow_html=True,
    )

    hint = st.session_state.get(KEY_VOICE_HINT) or st.session_state.get(KEY_VOICE_ERROR)
    if isinstance(hint, str) and hint.strip():
        tone = "warn" if "couldn't" in hint.lower() or "too large" in hint.lower() else "info"
        st.markdown(render_voice_hint_html(hint.strip(), tone=tone), unsafe_allow_html=True)
    elif not audio_ready and not has_transcript:
        st.markdown(
            render_voice_hint_html(MSG_NO_AUDIO, tone="info"),
            unsafe_allow_html=True,
        )

    transcribe_clicked = st.button(
        "Transcribe",
        key="ia_voice_transcribe_btn",
        type="primary",
        use_container_width=True,
        disabled=not audio_ready,
    )
    if transcribe_clicked:
        source = resolve_voice_audio_source(recorded, uploaded)
        if source is None:
            st.session_state[KEY_VOICE_HINT] = MSG_NO_AUDIO
            st.session_state[KEY_VOICE_STATUS] = voice_status_line(
                "ready", has_audio=False, has_transcript=has_transcript
            )
        else:
            audio_bytes, filename = source
            st.session_state[KEY_VOICE_STATUS] = voice_status_line(
                "ready",
                has_audio=audio_ready,
                has_transcript=has_transcript,
                transcribing=True,
            )
            st.session_state.pop(KEY_VOICE_HINT, None)
            with st.spinner("Transcribing…"):
                result = transcribe_audio(
                    audio_bytes,
                    filename=filename,
                    openai_api_key=session_openai_key(),
                    session_state=dict(st.session_state),
                )
            if result.ok:
                st.session_state[KEY_VOICE_TRANSCRIPT] = result.transcript
                st.session_state[KEY_VOICE_PHASE] = "transcribed"
                st.session_state[KEY_VOICE_HINT] = ""
                st.session_state[KEY_VOICE_STATUS] = voice_status_line(
                    "transcribed",
                    has_audio=audio_ready,
                    has_transcript=True,
                )
            else:
                st.session_state[KEY_VOICE_PHASE] = "ready"
                st.session_state[KEY_VOICE_HINT] = result.error or (
                    "We couldn't transcribe that clip. Try again or type your answer below."
                )
                st.session_state[KEY_VOICE_STATUS] = voice_status_line(
                    "ready", has_audio=audio_ready, has_transcript=has_transcript
                )
        st.rerun()


def _render_voice_transcript_draft(transcript: str) -> str | None:
    """Editable draft above chat input; returns text when user sends."""
    st.markdown(
        f'<p class="ia-voice-status">{voice_status_line("transcribed", has_audio=False, has_transcript=True)}</p>',
        unsafe_allow_html=True,
    )
    st.text_area(
        "Transcript draft",
        key=KEY_VOICE_TRANSCRIPT,
        height=88,
        placeholder="Edit your transcript before sending.",
        label_visibility="collapsed",
    )
    transcript = str(st.session_state.get(KEY_VOICE_TRANSCRIPT) or "")

    action_col, clear_col = st.columns([1.4, 0.6], gap="small")
    with action_col:
        send_clicked = st.button(
            "Send transcript",
            key="ia_voice_send_btn",
            type="primary",
            use_container_width=True,
            disabled=not transcript.strip(),
        )
    with clear_col:
        clear_clicked = st.button(
            "Clear",
            key="ia_voice_clear_btn",
            type="secondary",
            use_container_width=True,
        )

    if clear_clicked:
        clear_voice_transcript_draft(dict(st.session_state))
        st.rerun()

    if send_clicked and transcript.strip():
        text = transcript.strip()
        clear_voice_input_state(dict(st.session_state))
        return text
    return None


def render_voice_input_panel() -> str | None:
    """
    Render a compact voice composer above the mock interview chat input.

    Returns transcript text when the user clicks **Send transcript**; otherwise ``None``.
    Audio is never written to session storage — only the optional text draft key is used.
    """
    transcript, has_transcript, phase = _voice_phase_and_transcript()

    with st.container(key="ia_voice_composer"):
        voice_col, _ = st.columns([1.35, 4.65], gap="small", vertical_alignment="center")
        with voice_col:
            with st.popover("Voice answer", icon=":material/mic:"):
                recorded = st.audio_input(
                    "Record answer",
                    key="ia_voice_audio_input",
                )
                with st.expander("Upload audio instead", expanded=False):
                    uploaded = st.file_uploader(
                        "Upload audio",
                        type=list(_VOICE_UPLOAD_TYPES),
                        key="ia_voice_file_upload",
                        label_visibility="collapsed",
                        help="WAV, MP3, M4A, or WebM · max 25 MB",
                    )
                    st.caption(MSG_MIC_TIP.replace("**", ""))

                audio_ready = has_voice_audio_ready(recorded, uploaded)
                _render_voice_status_and_transcribe(
                    recorded,
                    uploaded,
                    audio_ready=audio_ready,
                    has_transcript=has_transcript,
                    phase=phase,
                )
                st.caption("Audio is transcribed only and not stored.")

        if has_transcript:
            return _render_voice_transcript_draft(transcript)

    return None
