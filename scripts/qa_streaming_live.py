#!/usr/bin/env python3
"""
Optional local manual QA for Mock Interview streaming (NOT run in CI).

Requires OPENAI_API_KEY in the environment or project-root `.env`.
Never prints secrets. Exits non-zero when the key is missing.

Usage:
    export OPENAI_API_KEY=sk-...
    python scripts/qa_streaming_live.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from interview_app.app.ui_settings import UISettings
from interview_app.config.settings import get_settings
from interview_app.services.chat_service import run_turn
from interview_app.services.mock_interview_flow import (
    InterviewState,
    MockInterviewPhase,
    classify_off_topic_category,
    init_mock_interview_runtime_state,
    set_mock_state,
)
from interview_app.utils.types import ChatMessage

PENDING = "How would you design a production-ready LLM application for interview coaching?"


def _load_api_key() -> bool:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        print("OPENAI_API_KEY is not set. Skipping live streaming QA.")
        return False
    os.environ["OPENAI_API_KEY"] = key
    get_settings.cache_clear()
    return True


def _settings() -> UISettings:
    return UISettings(
        role_category="Other",
        role_title="AI Engineer",
        seniority="Mid-Level",
        interview_round="Technical Interview",
        interview_focus="Technical Knowledge",
        job_description="",
        persona="Hiring Manager",
        question_difficulty_mode="auto",
        effective_question_difficulty="Medium",
        prompt_strategy="zero_shot",
        model_preset="gpt-4o-mini",
        temperature=0.2,
        top_p=1.0,
        max_tokens=800,
        show_debug=False,
        response_language="en",
        usage_mode="demo",
        byo_key_hint=None,
    )


def _seed_session() -> tuple[dict, list[ChatMessage]]:
    session: dict = {}
    init_mock_interview_runtime_state(session)
    set_mock_state(
        session,
        pending_question=PENDING,
        phase=MockInterviewPhase.AWAITING_ANSWER,
        interview_state=InterviewState.WAITING_FOR_ANSWER,
    )
    messages = [
        ChatMessage(role="user", content="I'm ready."),
        ChatMessage(role="assistant", content=f"First question:\n\n{PENDING}"),
    ]
    return session, messages


def _run_stream_case(name: str, user: str, *, session: dict, messages: list[ChatMessage]) -> bool:
    msgs = [*messages, ChatMessage(role="user", content=user)]
    out = run_turn(_settings(), msgs, session_state=session, enable_streaming=True)
    if out.stream is None:
        print(f"[FAIL] {name}: expected stream handle, got buffered reply")
        print(f"       preview: {(out.assistant_message or '')[:160]}")
        return False
    chunks: list[str] = []
    for chunk in out.stream:
        chunks.append(chunk)
    finalized = out.stream.finalize()
    print(f"[PASS] {name}: chunks={len(chunks)} total_chars={sum(len(c) for c in chunks)}")
    print(f"       usage: {finalized.usage_summary or '(latency-only or unavailable)'}")
    print(f"       final_preview: {finalized.assistant_message[:160]}")
    return True


def main() -> int:
    if not _load_api_key():
        return 2

    print("Live Mock Interview streaming QA (optional manual script)")
    print(f"ENABLE_STREAMING={get_settings().enable_streaming}")

    off = classify_off_topic_category("Hello, how are you today?")
    if off is not None:
        print(f"[FAIL] routing: small talk classified as {off}")
        return 1
    print("[PASS] routing: Hello, how are you today? is not live-data off-topic")

    session, base = _seed_session()
    ok = _run_stream_case(
        "clarification",
        "Can you explain what production ready means?",
        session=session,
        messages=base,
    )

    session2, base2 = _seed_session()
    ok = (
        _run_stream_case(
            "small talk",
            "Hello, how are you today?",
            session=session2,
            messages=base2,
        )
        and ok
    )

    print("SUMMARY:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
