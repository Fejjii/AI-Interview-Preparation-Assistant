"""Mock Interview voice answer input (record/upload → auto-transcribe → review → send)."""

from __future__ import annotations

import hashlib
from typing import Any, Callable, Literal

import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

from interview_app.app.tabs.shared import session_openai_key
from interview_app.services.transcription_service import TranscriptionResult, transcribe_audio

KEY_VOICE_TRANSCRIPT = "ia_voice_transcript_draft"
KEY_VOICE_STATUS = "ia_voice_status_message"
KEY_VOICE_HINT = "ia_voice_hint_message"
KEY_VOICE_PHASE = "ia_voice_phase"
KEY_VOICE_PROCESSED_HASH = "ia_voice_processed_audio_hash"
KEY_VOICE_PANEL_OPEN = "ia_voice_panel_open"
KEY_VOICE_AUTO_SEND = "ia_voice_auto_send"
KEY_VOICE_AUTO_SEND_PENDING = "ia_voice_auto_send_pending"

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
        KEY_VOICE_PROCESSED_HASH,
        KEY_VOICE_AUTO_SEND_PENDING,
        KEY_VOICE_ERROR,
    ):
        session_state.pop(key, None)
    for widget_key in (
        "ia_voice_audio_input",
        "ia_voice_file_upload",
        "ia_voice_send_btn",
        "ia_voice_clear_btn",
        "ia_voice_retry_btn",
        "ia_voice_toggle_btn",
        "ia_voice_auto_send",
    ):
        session_state.pop(widget_key, None)


def clear_voice_transcript_draft(session_state: dict[str, Any]) -> None:
    """Clear review text and hints without resetting capture widgets."""
    session_state[KEY_VOICE_TRANSCRIPT] = ""
    session_state[KEY_VOICE_STATUS] = voice_status_line(
        "ready", has_audio=False, has_transcript=False
    )
    session_state[KEY_VOICE_PHASE] = "ready"
    session_state.pop(KEY_VOICE_HINT, None)
    session_state.pop(KEY_VOICE_ERROR, None)
    session_state.pop(KEY_VOICE_PROCESSED_HASH, None)
    session_state.pop(KEY_VOICE_AUTO_SEND_PENDING, None)


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


def voice_audio_fingerprint(audio_bytes: bytes, filename: str) -> str:
    """Stable hash for deduplicating auto-transcription on Streamlit reruns."""
    digest = hashlib.sha256()
    digest.update(audio_bytes)
    digest.update(b"\0")
    digest.update(filename.encode("utf-8"))
    return digest.hexdigest()


def needs_auto_transcription(session_state: dict[str, Any], audio_hash: str) -> bool:
    """Return True when this audio has not yet been auto-transcribed."""
    if not audio_hash:
        return False
    return session_state.get(KEY_VOICE_PROCESSED_HASH) != audio_hash


def voice_has_transcription_error(session_state: dict[str, Any]) -> bool:
    hint = session_state.get(KEY_VOICE_HINT) or session_state.get(KEY_VOICE_ERROR)
    return isinstance(hint, str) and bool(hint.strip())


def resolve_voice_display_status(
    session_state: dict[str, Any],
    *,
    audio_ready: bool,
    has_transcript: bool,
    audio_hash: str | None,
) -> str | None:
    """
    Return a compact status line for the voice mini-panel.

    Never returns a persistent ``Transcribing…`` label — that state is shown only
    via ``st.spinner`` while the API call is in flight.
    """
    if has_transcript:
        return voice_status_line("transcribed", has_audio=audio_ready, has_transcript=True)
    if voice_has_transcription_error(session_state):
        return None
    if not audio_ready:
        return None
    if audio_hash and session_state.get(KEY_VOICE_PROCESSED_HASH) == audio_hash:
        return None
    return voice_status_line("ready", has_audio=True, has_transcript=False)


def apply_transcription_result(
    session_state: dict[str, Any],
    result: TranscriptionResult,
    *,
    audio_hash: str,
    has_audio: bool,
) -> None:
    """Persist transcript or a friendly error after one transcription attempt."""
    session_state[KEY_VOICE_PROCESSED_HASH] = audio_hash
    transcript = (result.transcript or "").strip()
    if result.ok and transcript:
        session_state[KEY_VOICE_TRANSCRIPT] = transcript
        session_state[KEY_VOICE_PHASE] = "transcribed"
        session_state[KEY_VOICE_HINT] = ""
        session_state[KEY_VOICE_STATUS] = voice_status_line(
            "transcribed",
            has_audio=has_audio,
            has_transcript=True,
        )
        return

    session_state[KEY_VOICE_PHASE] = "ready"
    session_state[KEY_VOICE_TRANSCRIPT] = ""
    session_state[KEY_VOICE_HINT] = result.error or (
        "We couldn't transcribe that clip. Try again or type your answer below."
    )
    if result.ok and not transcript:
        session_state[KEY_VOICE_HINT] = "No speech detected. Try again or type your answer."
    session_state[KEY_VOICE_STATUS] = voice_status_line(
        "ready", has_audio=has_audio, has_transcript=False
    )


def run_auto_transcription_if_needed(
    session_state: dict[str, Any],
    audio_bytes: bytes,
    filename: str,
    *,
    openai_api_key: str | None,
    transcribe_fn: Callable[..., TranscriptionResult] = transcribe_audio,
) -> bool:
    """
    Transcribe new audio once per fingerprint.

    Returns ``True`` when a transcription attempt was made.
    """
    audio_hash = voice_audio_fingerprint(audio_bytes, filename)
    if not needs_auto_transcription(session_state, audio_hash):
        return False

    session_state.pop(KEY_VOICE_HINT, None)
    session_state.pop(KEY_VOICE_ERROR, None)
    result = transcribe_fn(
        audio_bytes,
        filename=filename,
        openai_api_key=openai_api_key,
        session_state=session_state,
    )
    apply_transcription_result(
        session_state,
        result,
        audio_hash=audio_hash,
        has_audio=True,
    )
    return True


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


def _voice_phase_and_transcript(session_state: dict[str, Any]) -> tuple[str, bool]:
    if KEY_VOICE_TRANSCRIPT not in session_state:
        session_state[KEY_VOICE_TRANSCRIPT] = ""
    transcript = str(session_state.get(KEY_VOICE_TRANSCRIPT) or "")
    return transcript, bool(transcript.strip())


def _maybe_return_auto_send(session_state: dict[str, Any]) -> str | None:
    if not session_state.pop(KEY_VOICE_AUTO_SEND_PENDING, False):
        return None
    transcript = str(session_state.get(KEY_VOICE_TRANSCRIPT) or "").strip()
    if not transcript:
        return None
    clear_voice_input_state(session_state)
    return transcript


def _handle_auto_transcription(
    session_state: dict[str, Any],
    audio_bytes: bytes,
    filename: str,
    *,
    audio_hash: str,
) -> None:
    if not needs_auto_transcription(session_state, audio_hash):
        return
    with st.spinner("Transcribing…"):
        run_auto_transcription_if_needed(
            session_state,
            audio_bytes,
            filename,
            openai_api_key=session_openai_key(),
        )
    if (
        session_state.get(KEY_VOICE_AUTO_SEND)
        and str(session_state.get(KEY_VOICE_TRANSCRIPT) or "").strip()
    ):
        session_state[KEY_VOICE_AUTO_SEND_PENDING] = True
    st.rerun()


def render_voice_input_panel() -> str | None:
    """
    Render a compact voice control beside the mock interview chat composer.

    Returns transcript text when the user clicks **Send transcript** (or auto-send
    is enabled); otherwise ``None``. Audio is never written to session storage.
    """
    session_state = st.session_state
    if KEY_VOICE_PANEL_OPEN not in session_state:
        session_state[KEY_VOICE_PANEL_OPEN] = False

    pending_auto_send = _maybe_return_auto_send(session_state)
    if pending_auto_send:
        return pending_auto_send

    _, voice_btn_col = st.columns([5, 1], gap="small", vertical_alignment="center")
    with voice_btn_col:
        if st.button(
            "Voice",
            key="ia_voice_toggle_btn",
            type="secondary",
            icon=":material/mic:",
            use_container_width=True,
        ):
            session_state[KEY_VOICE_PANEL_OPEN] = not bool(session_state.get(KEY_VOICE_PANEL_OPEN))

    if not session_state.get(KEY_VOICE_PANEL_OPEN):
        return None

    transcript, has_transcript = _voice_phase_and_transcript(session_state)

    with st.container(key="ia_voice_mini"):
        recorded = st.audio_input(
            "Record answer",
            key="ia_voice_audio_input",
            label_visibility="collapsed",
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

        st.checkbox(
            "Auto-send after transcription",
            key=KEY_VOICE_AUTO_SEND,
            value=False,
            help="Off by default — review and edit the transcript before sending.",
        )

        source = resolve_voice_audio_source(recorded, uploaded)
        audio_ready = source is not None
        audio_hash = voice_audio_fingerprint(source[0], source[1]) if source is not None else None

        if not audio_ready and not has_transcript:
            st.caption("Record or upload a short answer.")

        if source is not None and audio_hash is not None:
            processed_hash = session_state.get(KEY_VOICE_PROCESSED_HASH)
            hint = session_state.get(KEY_VOICE_HINT) or session_state.get(KEY_VOICE_ERROR)
            failed = (
                isinstance(hint, str)
                and hint.strip()
                and not has_transcript
                and processed_hash == audio_hash
            )

            if failed:
                st.markdown(
                    render_voice_hint_html(hint.strip(), tone="warn"),
                    unsafe_allow_html=True,
                )
                if st.button(
                    "Retry",
                    key="ia_voice_retry_btn",
                    type="secondary",
                ):
                    session_state.pop(KEY_VOICE_PROCESSED_HASH, None)
                    session_state.pop(KEY_VOICE_HINT, None)
                    session_state.pop(KEY_VOICE_ERROR, None)
                    session_state.pop(KEY_VOICE_STATUS, None)
                    st.rerun()
            else:
                _handle_auto_transcription(
                    session_state,
                    source[0],
                    source[1],
                    audio_hash=audio_hash,
                )

        transcript, has_transcript = _voice_phase_and_transcript(session_state)
        status = resolve_voice_display_status(
            session_state,
            audio_ready=audio_ready,
            has_transcript=has_transcript,
            audio_hash=audio_hash,
        )
        if status:
            st.markdown(
                f'<p class="ia-voice-status">{status}</p>',
                unsafe_allow_html=True,
            )

        if has_transcript:
            st.text_area(
                "Transcript draft",
                key=KEY_VOICE_TRANSCRIPT,
                height=72,
                placeholder="Edit your transcript before sending.",
                label_visibility="collapsed",
            )
            transcript = str(session_state.get(KEY_VOICE_TRANSCRIPT) or "")

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
                clear_voice_input_state(session_state)
                st.rerun()

            if send_clicked and transcript.strip():
                text = transcript.strip()
                clear_voice_input_state(session_state)
                return text

    return None
