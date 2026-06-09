"""Usage mode (Demo vs Bring Your Own OpenAI key) — session keys and validation.

Secrets live only in ``st.session_state`` for the active Streamlit session (server-side
in-memory for that browser session). They are never written to disk, localStorage,
or sessionStorage by this app.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

KEY_USAGE_MODE = "ia_usage_mode"
# In-memory only; never log or serialize.
KEY_BYO_OPENAI_API_KEY = "ia_byo_openai_api_key_secret"
# Truncated fingerprint for UI, e.g. sk-...a1b2
KEY_BYO_KEY_HINT = "ia_byo_key_display_hint"
# Sidebar widget: selected label before Apply.
KEY_USAGE_DRAFT_RADIO = "um_draft_radio"
# Demo-mode LLM call counter (in-memory per Streamlit browser session).
KEY_DEMO_LLM_CALL_COUNT = "ia_demo_llm_call_count"

DEMO_LIMIT_MESSAGE = (
    "Demo usage limit reached for this session. "
    "You can refresh later or use your own OpenAI API key."
)


class UsageMode(str, Enum):
    """How API calls are billed for this browser session."""

    DEMO = "demo"
    BYO = "byo"


def init_usage_mode_defaults(session_state: dict[str, Any]) -> None:
    """Ensure usage mode defaults to Demo until the user applies another mode."""
    if KEY_USAGE_MODE not in session_state:
        session_state[KEY_USAGE_MODE] = UsageMode.DEMO.value
    if KEY_USAGE_DRAFT_RADIO not in session_state:
        session_state[KEY_USAGE_DRAFT_RADIO] = (
            "Demo access"
            if session_state[KEY_USAGE_MODE] == UsageMode.DEMO.value
            else "Use my own OpenAI key"
        )


def validate_openai_api_key_format(key: str) -> tuple[bool, str]:
    """
    Basic format checks only; does not verify the key with OpenAI.

    Returns:
        (True, "") when valid-looking, else (False, user-facing error).
    """
    s = (key or "").strip()
    if not s:
        return False, "Enter your OpenAI API key, or switch to Demo access."
    if not s.startswith("sk-"):
        return False, "OpenAI API keys must start with sk-."
    if len(s) < 20:
        return False, "That API key looks too short."
    if len(s) > 512:
        return False, "That API key looks invalid (too long)."
    if not re.fullmatch(r"sk-[a-zA-Z0-9_-]+", s):
        return False, "The API key contains invalid characters."
    return True, ""


def mask_api_key_for_display(key: str) -> str:
    """Return a non-reversible fingerprint like sk-...A1b2 for status UI."""
    s = (key or "").strip()
    if len(s) < 12:
        return "sk-..."
    tail = s[-4:]
    return f"sk-...{tail}"


def key_tail_from_masked_hint(masked: str) -> str | None:
    """Last four characters of the key from ``mask_api_key_for_display`` output."""
    s = (masked or "").strip()
    if len(s) < 4:
        return None
    return s[-4:]


def openai_api_key_for_llm(session_state: dict[str, Any]) -> str | None:
    """
    Resolve which API key to pass into ``LLMClient``.

    Returns:
        ``None`` for Demo mode (use configured ``OPENAI_API_KEY`` from settings/env).
        A non-empty string for BYO mode.
    """
    mode = str(session_state.get(KEY_USAGE_MODE) or UsageMode.DEMO.value)
    if mode == UsageMode.BYO.value:
        raw = session_state.get(KEY_BYO_OPENAI_API_KEY)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        return None
    return None


def demo_mode_backend_key_configured() -> bool:
    """True when the server has a project API key for Demo mode."""
    from interview_app.config.settings import get_settings

    s = get_settings()
    if s.openai_api_key is None:
        return False
    v = s.openai_api_key.get_secret_value()
    return bool(v and str(v).strip())


def is_demo_usage_mode(session_state: dict[str, Any]) -> bool:
    """True when the active session bills API calls against the shared demo key."""
    mode = str(session_state.get(KEY_USAGE_MODE) or UsageMode.DEMO.value)
    return mode == UsageMode.DEMO.value


def get_demo_max_llm_calls() -> int:
    """Configured per-session demo LLM call cap (from settings / env)."""
    from interview_app.config.settings import get_settings

    return get_settings().demo_max_llm_calls_per_session


def get_demo_usage_count(session_state: dict[str, Any]) -> int:
    """Number of successful demo LLM calls recorded for this browser session."""
    raw = session_state.get(KEY_DEMO_LLM_CALL_COUNT, 0)
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 0


def demo_remaining_calls(session_state: dict[str, Any]) -> int | None:
    """
    Remaining demo LLM calls for this session, or ``None`` when not in demo mode.
    """
    if not is_demo_usage_mode(session_state):
        return None
    return max(0, get_demo_max_llm_calls() - get_demo_usage_count(session_state))


def demo_usage_limit_reached(session_state: dict[str, Any]) -> bool:
    """True when demo mode is active and the session call cap has been reached."""
    if not is_demo_usage_mode(session_state):
        return False
    return get_demo_usage_count(session_state) >= get_demo_max_llm_calls()


def increment_demo_usage_count(session_state: dict[str, Any]) -> int:
    """
    Record one successful demo LLM call. No-op outside demo mode.

    Returns the updated count.
    """
    if not is_demo_usage_mode(session_state):
        return get_demo_usage_count(session_state)
    count = get_demo_usage_count(session_state) + 1
    session_state[KEY_DEMO_LLM_CALL_COUNT] = count
    return count


def maybe_block_demo_llm_call(session_state: dict[str, Any] | None) -> str | None:
    """
    Return the user-facing limit message when a demo LLM call should be blocked.

    Returns ``None`` when the call may proceed (BYO mode or under the cap).
    """
    if session_state is None or not is_demo_usage_mode(session_state):
        return None
    if demo_usage_limit_reached(session_state):
        return DEMO_LIMIT_MESSAGE
    return None


def record_demo_llm_call(session_state: dict[str, Any] | None) -> None:
    """Increment the demo usage counter after a successful OpenAI API call."""
    if session_state is not None:
        increment_demo_usage_count(session_state)
