from __future__ import annotations

"""
Lightweight pattern-based content moderation.

Detects obviously unsafe, abusive, or off-limits content. Intentionally simple
and easy to extend—no external moderation API required.
"""

import re
from typing import Final

from pydantic import BaseModel, Field

from interview_app.config.settings import get_security_settings
from interview_app.security.logging import log_security_event

_CATEGORY_PATTERNS: Final[dict[str, list[re.Pattern[str]]]] = {
    "hate_speech": [
        re.compile(r"\b(kill\s+all|exterminate|ethnic\s+cleansing)\b", re.IGNORECASE),
        re.compile(r"\bracist\s+(joke|slur)s?\b", re.IGNORECASE),
        re.compile(r"\b(racial\s+supremacy|white\s+power|heil\s+hitler)\b", re.IGNORECASE),
    ],
    "violence": [
        re.compile(r"\b(how\s+to\s+(make|build)\s+a?\s*(bomb|weapon|explosive))\b", re.IGNORECASE),
        re.compile(r"\b(instructions?\s+(for|to)\s+(kill|murder|assassinat))\b", re.IGNORECASE),
        re.compile(r"\b(mass\s+(shooting|murder|violence)\s+plan)\b", re.IGNORECASE),
    ],
    "sexual_content": [
        re.compile(
            r"\bwrite\s+.{0,20}(explicit|erotic)\s+(sexual\s+)?(story|content|fiction)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(explicit|erotic)\s+sexual\s+(story|content|fiction|roleplay)\b", re.IGNORECASE
        ),
        re.compile(r"\b(sexual\s+(roleplay|fantasy)\s+(with|about)\s+minor)\b", re.IGNORECASE),
    ],
    "illegal_activity": [
        re.compile(
            r"\b(how\s+to\s+(hack|crack|break\s+into)\s+(a\s+)?(bank|system|account))\b",
            re.IGNORECASE,
        ),
        re.compile(r"\b(synthesize|manufacture)\s+(meth|fentanyl|drugs)\b", re.IGNORECASE),
        re.compile(
            r"\b(credit\s+card\s+fraud|identity\s+theft)\s+(tutorial|guide|how)\b", re.IGNORECASE
        ),
    ],
}


class ModerationResult(BaseModel):
    """Outcome of a moderation check."""

    safe: bool
    category: str | None = None
    matched_snippet: str = ""
    message: str = ""
    flags: list[str] = Field(default_factory=list)


def check_moderation(
    text: str,
    *,
    service: str = "unknown",
) -> ModerationResult:
    """
    Scan text for obviously unsafe content patterns.

    Returns ``ModerationResult(safe=True)`` for clean content. When unsafe
    content is detected the result includes the matched category and a
    user-facing message.
    """
    sec = get_security_settings()
    if not sec.moderation_enabled:
        return ModerationResult(safe=True)

    if not text or not text.strip():
        return ModerationResult(safe=True)

    for category, patterns in _CATEGORY_PATTERNS.items():
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                snippet = match.group(0)[:60]
                log_security_event(
                    event="moderation",
                    action="blocked",
                    reason=f"Category: {category}",
                    service=service,
                    matched_pattern=snippet,
                )
                return ModerationResult(
                    safe=False,
                    category=category,
                    matched_snippet=snippet,
                    message=_user_message_for(category),
                    flags=[f"moderation:{category}"],
                )

    return ModerationResult(safe=True)


_CATEGORY_MESSAGES: Final[dict[str, str]] = {
    "hate_speech": "Your message was blocked because it appears to contain hateful or discriminatory content.",
    "violence": "Your message was blocked because it appears to reference violent or dangerous content.",
    "sexual_content": "Your message was blocked because it appears to contain inappropriate sexual content.",
    "illegal_activity": "Your message was blocked because it appears to reference illegal activity.",
}


def _user_message_for(category: str) -> str:
    return _CATEGORY_MESSAGES.get(
        category,
        "Your message was blocked by our content policy. Please rephrase.",
    )
