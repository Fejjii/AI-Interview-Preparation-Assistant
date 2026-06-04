"""CV prompt boundary tokens (shared by prompt builders and text sanitization)."""

from __future__ import annotations

CV_BEGIN = "<<<CV_TEXT_BEGIN>>>"
CV_END = "<<<CV_TEXT_END>>>"

# Substrings used by guardrails to detect delimiter breakout in untrusted user text.
CV_DELIMITER_MARKERS: tuple[str, ...] = (
    CV_BEGIN.lower(),
    CV_END.lower(),
    "<<<cv_text",
    "<<<system",
    "<<<user",
    "<<<assistant",
)
