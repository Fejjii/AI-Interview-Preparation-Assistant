from __future__ import annotations

"""
Centralized safe error handling.

Provides custom exception types and a helper to convert any exception into a
clean, user-facing message. Raw backend details (stack traces, API internals,
config values, prompt content) are never exposed in the UI.
"""

import logging
from typing import Final

from interview_app.security.redaction import redact_secrets

logger = logging.getLogger("interview_app.errors")

_GENERIC_USER_MESSAGE: Final[str] = "Something went wrong. Please try again or adjust your inputs."


class AppError(Exception):
    """Base exception for application-level errors with a safe user message."""

    def __init__(self, user_message: str, *, internal_detail: str | None = None) -> None:
        self.user_message = user_message
        self.internal_detail = internal_detail or user_message
        super().__init__(self.internal_detail)


class GuardrailError(AppError):
    """Raised when a guardrail check blocks a request."""


class RateLimitError(AppError):
    """Raised when session rate limit is exceeded."""


class ModerationError(AppError):
    """Raised when content moderation blocks a request."""


class OutputValidationError(AppError):
    """Raised when model output fails validation."""


def safe_user_message(exc: BaseException) -> str:
    """
    Return a clean message suitable for display in the UI.

    - AppError subclasses: use the explicit user_message.
    - OpenAI API errors: return a generic API error hint.
    - Everything else: return a generic fallback.
    """
    if isinstance(exc, AppError):
        return exc.user_message

    _log_internal_error(exc)

    exc_type = type(exc).__name__
    exc_type_lower = exc_type.lower()
    lowered = str(exc).lower()
    if "insufficient_quota" in lowered or "billing_hard_limit" in lowered:
        return (
            "Billing or quota is not available for this API key. Check your OpenAI account "
            "billing settings and plan limits."
        )
    if "authentication" in exc_type_lower or "permissiondenied" in exc_type_lower:
        return (
            "Authentication failed. If you use your own API key, check it and apply again. "
            "Otherwise ensure Demo mode has a valid server API key."
        )
    if "ratelimit" in exc_type_lower or "rate_limit" in exc_type_lower:
        return (
            "The AI provider rate limit or quota was reached. Wait a moment or check billing "
            "on your OpenAI account (BYO mode) or try again later."
        )
    if "openai" in type(exc).__module__.lower() if hasattr(type(exc), "__module__") else False:
        return "The AI service is temporarily unavailable. Please try again shortly."
    if "timeout" in exc_type_lower or "Timeout" in exc_type:
        return "The request timed out. Please try again."
    return _GENERIC_USER_MESSAGE


def _log_internal_error(exc: BaseException) -> None:
    """Log the real exception details internally (no secrets in log)."""
    safe_detail = redact_secrets(str(exc))[:500]
    logger.error(
        "Internal error: %s: %s",
        type(exc).__name__,
        safe_detail,
        exc_info=False,
    )
