from __future__ import annotations

import re
import unicodedata

from interview_app.cv.delimiters import CV_BEGIN, CV_END


def strip_cv_prompt_delimiters(text: str) -> str:
    """
    Remove CV delimiter tokens from untrusted resume text before prompt injection.

    Prevents delimiter breakout where resume content closes the fenced region early
    and appends attacker-controlled instructions.
    """
    if not text:
        return ""
    out = text
    for token in (CV_BEGIN, CV_END):
        if token in out:
            out = out.replace(token, "")
    return out


def normalize_cv_text(raw: str) -> str:
    """
    Normalize extracted CV text for downstream guardrails and LLM input.

    - Unicode normalize (NFKC)
    - Strip control characters except newlines/tabs
    - Collapse excessive blank lines and spaces
    """
    if not raw:
        return ""

    text = unicodedata.normalize("NFKC", raw)
    # Keep printable + common whitespace; drop other controls.
    cleaned_chars: list[str] = []
    for ch in text:
        if ch in ("\n", "\r", "\t"):
            cleaned_chars.append("\n" if ch == "\r" else ch)
            continue
        cat = unicodedata.category(ch)
        if cat == "Cc":
            continue
        cleaned_chars.append(ch)

    text = "".join(cleaned_chars)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse 3+ newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse long runs of spaces on each line
    lines = [" ".join(line.split()) for line in text.split("\n")]
    text = "\n".join(lines)
    return strip_cv_prompt_delimiters(text.strip())
