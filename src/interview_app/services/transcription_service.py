"""OpenAI speech-to-text for Mock Interview voice answers.

Audio is processed in memory only; callers must not persist raw bytes to disk or
session JSON. Transcription counts as one demo LLM/API call when in Demo mode.
"""

from __future__ import annotations

import io
import logging
import time
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from interview_app.app.usage_mode import maybe_block_demo_llm_call, record_demo_llm_call
from interview_app.config.settings import Settings, get_settings
from interview_app.utils.errors import safe_user_message
from interview_app.utils.types import LLMUsage

logger = logging.getLogger("interview_app.transcription")

ALLOWED_AUDIO_EXTENSIONS = frozenset({"wav", "mp3", "m4a", "webm", "mpeg", "mp4", "ogg", "oga"})

MSG_NO_AUDIO = "Add a short recording or audio file, then tap Transcribe audio."
MSG_UNSUPPORTED_FORMAT = "That file type isn't supported. Try WAV, MP3, M4A, or WebM."
MSG_MISSING_API_KEY = (
    "No API key is available. Switch to Demo access or apply your OpenAI key in the sidebar."
)


@dataclass(frozen=True)
class TranscriptionResult:
    """Typed outcome from a single transcription request."""

    ok: bool
    transcript: str = ""
    provider: str = "openai"
    model: str = ""
    latency_ms: float | None = None
    usage: LLMUsage | None = None
    error: str | None = None


def _resolve_api_key(settings: Settings, openai_api_key: str | None) -> str:
    if openai_api_key and str(openai_api_key).strip():
        return str(openai_api_key).strip()
    if settings.openai_api_key is not None:
        secret = settings.openai_api_key.get_secret_value()
        if secret and str(secret).strip():
            return str(secret).strip()
    raise ValueError(MSG_MISSING_API_KEY)


def file_extension(filename: str) -> str:
    name = (filename or "").strip()
    if "." not in name:
        return ""
    return name.rsplit(".", 1)[-1].lower()


def is_supported_audio_filename(filename: str) -> bool:
    ext = file_extension(filename)
    return not ext or ext in ALLOWED_AUDIO_EXTENSIONS


def _normalize_filename(filename: str) -> str:
    name = (filename or "recording.webm").strip()
    if "." not in name:
        return f"{name}.webm"
    ext = file_extension(name)
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        return f"{name}.webm"
    return name


def _log_transcription_audit(
    *,
    model: str,
    success: bool,
    latency_ms: float,
    error_type: str | None = None,
) -> None:
    entry: dict[str, Any] = {
        "event": "transcription",
        "route": "voice_input",
        "model": model,
        "success": success,
        "latency_ms": round(latency_ms, 2),
    }
    if error_type:
        entry["error_type"] = error_type
    if success:
        logger.info("Transcription %s", entry)
    else:
        logger.warning("Transcription %s", entry)


def transcribe_audio(
    audio_bytes: bytes,
    *,
    filename: str = "recording.webm",
    openai_api_key: str | None = None,
    session_state: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> TranscriptionResult:
    """
    Transcribe short interview answer audio via OpenAI.

    Respects demo usage limits (one API call per successful transcription).
    """
    cfg = settings or get_settings()
    model = cfg.openai_transcription_model
    max_bytes = cfg.security.voice_max_audio_bytes

    if not audio_bytes:
        return TranscriptionResult(ok=False, error=MSG_NO_AUDIO)

    if not is_supported_audio_filename(filename):
        return TranscriptionResult(ok=False, error=MSG_UNSUPPORTED_FORMAT)

    if len(audio_bytes) > max_bytes:
        mb = max(1, max_bytes // (1024 * 1024))
        return TranscriptionResult(
            ok=False,
            error=f"That clip is too large — please keep it under {mb} MB.",
        )

    blocked = maybe_block_demo_llm_call(session_state)
    if blocked:
        return TranscriptionResult(ok=False, error=blocked)

    try:
        api_key = _resolve_api_key(cfg, openai_api_key)
    except ValueError as exc:
        return TranscriptionResult(ok=False, error=str(exc))

    safe_name = _normalize_filename(filename)
    client = OpenAI(api_key=api_key, max_retries=cfg.openai_max_retries)
    t0 = time.monotonic()
    try:
        resp = client.audio.transcriptions.create(
            model=model,
            file=(safe_name, io.BytesIO(audio_bytes)),
            response_format="text",
        )
    except Exception as exc:
        latency_ms = (time.monotonic() - t0) * 1000.0
        _log_transcription_audit(
            model=model, success=False, latency_ms=latency_ms, error_type=type(exc).__name__
        )
        return TranscriptionResult(
            ok=False,
            model=model,
            latency_ms=latency_ms,
            error=safe_user_message(exc),
        )

    latency_ms = (time.monotonic() - t0) * 1000.0
    text = (resp if isinstance(resp, str) else getattr(resp, "text", "") or "").strip()
    _log_transcription_audit(model=model, success=True, latency_ms=latency_ms)
    record_demo_llm_call(session_state)

    return TranscriptionResult(
        ok=True,
        transcript=text,
        provider="openai",
        model=model,
        latency_ms=latency_ms,
        usage=None,
    )
