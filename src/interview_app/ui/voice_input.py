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

# Legacy key — cleared on reset for older sessions.
KEY_VOICE_ERROR = "ia_voice_last_error"

_VOICE_UPLOAD_TYPES = ("wav", "mp3", "m4a", "webm", "mpeg", "mp4", "ogg")
VoicePhase = Literal["ready", "transcribed"]

MSG_INLINE_HELP = "Record a short answer. We transcribe it into editable text before sending."
MSG_INLINE_HINT = "Record or upload a short answer."
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
        KEY_VOICE_ERROR,
    ):
        session_state.pop(key, None)
    for widget_key in (
        "ia_voice_audio_input",
        "ia_voice_file_upload",
        "ia_voice_send_btn",
        "ia_voice_clear_btn",
        "ia_voice_retry_btn",
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


def apply_transcription_result(
    session_state: dict[str, Any],
    result: TranscriptionResult,
    *,
    audio_hash: str,
    has_audio: bool,
) -> None:
    """Persist transcript or a friendly error after one transcription attempt."""
    session_state[KEY_VOICE_PROCESSED_HASH] = audio_hash
    if result.ok:
        session_state[KEY_VOICE_TRANSCRIPT] = result.transcript
        session_state[KEY_VOICE_PHASE] = "transcribed"
        session_state[KEY_VOICE_HINT] = ""
        session_state[KEY_VOICE_STATUS] = voice_status_line(
            "transcribed",
            has_audio=has_audio,
            has_transcript=True,
        )
        return

    session_state[KEY_VOICE_PHASE] = "ready"
    session_state[KEY_VOICE_HINT] = result.error or (
        "We couldn't transcribe that clip. Try again or type your answer below."
    )
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

    session_state[KEY_VOICE_STATUS] = voice_status_line(
        "ready",
        has_audio=True,
        has_transcript=False,
        transcribing=True,
    )
    session_state.pop(KEY_VOICE_HINT, None)
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


def _render_inline_status(has_transcript: bool, *, transcribing: bool = False) -> None:
    status_line = str(st.session_state.get(KEY_VOICE_STATUS) or "").strip()
    if not status_line:
        status_line = voice_status_line(
            "transcribed" if has_transcript else "ready",
            has_audio=False,
            has_transcript=has_transcript,
            transcribing=transcribing,
        )
    st.markdown(
        f'<p class="ia-voice-status">{status_line}</p>',
        unsafe_allow_html=True,
    )


def render_voice_input_panel() -> str | None:
    """
    Render an inline voice composer above the mock interview chat input.

    Returns transcript text when the user clicks **Send transcript**; otherwise ``None``.
    Audio is never written to session storage — only the optional text draft key is used.
    """
    transcript, has_transcript, _phase = _voice_phase_and_transcript()

    with st.container(border=True, key="ia_voice_inline"):
        st.markdown(
            '<p class="ia-voice-inline-title">Voice answer</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<p class="ia-voice-inline-help">{MSG_INLINE_HELP}</p>',
            unsafe_allow_html=True,
        )

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

        source = resolve_voice_audio_source(recorded, uploaded)
        audio_ready = source is not None

        if not audio_ready and not has_transcript:
            st.markdown(
                render_voice_hint_html(MSG_INLINE_HINT, tone="info"),
                unsafe_allow_html=True,
            )

        if source is not None:
            audio_bytes, filename = source
            audio_hash = voice_audio_fingerprint(audio_bytes, filename)
            processed_hash = st.session_state.get(KEY_VOICE_PROCESSED_HASH)
            hint = st.session_state.get(KEY_VOICE_HINT) or st.session_state.get(KEY_VOICE_ERROR)
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
                    "Retry transcription",
                    key="ia_voice_retry_btn",
                    type="secondary",
                    use_container_width=True,
                ):
                    st.session_state.pop(KEY_VOICE_PROCESSED_HASH, None)
                    st.session_state.pop(KEY_VOICE_HINT, None)
                    st.session_state.pop(KEY_VOICE_ERROR, None)
                    st.rerun()
            elif needs_auto_transcription(dict(st.session_state), audio_hash):
                with st.spinner("Transcribing…"):
                    run_auto_transcription_if_needed(
                        dict(st.session_state),
                        audio_bytes,
                        filename,
                        openai_api_key=session_openai_key(),
                    )
                st.rerun()

        transcript, has_transcript, _phase = _voice_phase_and_transcript()

        if has_transcript:
            _render_inline_status(has_transcript=True)
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
                clear_voice_input_state(dict(st.session_state))
                st.rerun()

            if send_clicked and transcript.strip():
                text = transcript.strip()
                clear_voice_input_state(dict(st.session_state))
                return text
        elif audio_ready and not (
            st.session_state.get(KEY_VOICE_HINT) or st.session_state.get(KEY_VOICE_ERROR)
        ):
            _render_inline_status(has_transcript=False, transcribing=True)

        st.caption("Audio is transcribed only and not stored.")

    return None
