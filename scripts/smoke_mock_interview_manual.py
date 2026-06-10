#!/usr/bin/env python3
"""Local manual smoke check for mock interview routing (no live OpenAI calls)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from interview_app.app.ui_settings import UISettings
from interview_app.security.pipeline import InputPipelineResult
from interview_app.services.answer_evaluator import EvaluateAnswerResult
from interview_app.services.chat_service import run_turn
from interview_app.services.interview_generator import GenerateQuestionsResult
from interview_app.services.mock_interview_flow import clear_mock_interview_runtime_state
from interview_app.storage.sessions import delete_session, list_sessions, save_session
from interview_app.utils.types import ChatMessage, EvaluationResult, LLMResponse, SessionMeta

Q1 = "How would you design a production-ready LLM application for interview coaching?"
Q2 = "What guardrails would you add before exposing an LLM feature to end users?"
Q3 = "How do you validate prompt strategy changes without relying only on manual testing?"
PENDING_AFTER_OFF_TOPIC = Q3


def _settings() -> UISettings:
    return UISettings(
        role_category="Other",
        role_title="AI Engineer",
        seniority="Mid-Level",
        interview_round="Technical Interview",
        interview_focus="Technical Knowledge",
        job_description="",
        persona="Hiring Manager",
        question_difficulty_mode="Auto",
        effective_question_difficulty="Medium",
        prompt_strategy="chain_of_thought",
        model_preset="gpt-4o-mini",
        temperature=0.15,
        top_p=0.95,
        max_tokens=900,
        show_debug=False,
        response_language="en",
        usage_mode="demo",
        byo_key_hint=None,
    )


def _question_result(text: str) -> GenerateQuestionsResult:
    return GenerateQuestionsResult(
        ok=True,
        response=LLMResponse(text=text, model="gpt-4o-mini", usage=None, raw_response_id=None),
        error=None,
        guardrails={},
        prompt=None,
    )


def _eval_result(follow_up: str) -> EvaluateAnswerResult:
    return EvaluateAnswerResult(
        ok=True,
        response=LLMResponse(text="graded", model="gpt-4o-mini", usage=None, raw_response_id=None),
        error=None,
        guardrails={},
        system_prompt="sys",
        user_prompt="user",
        evaluation=EvaluationResult(
            score=8,
            criteria_met=["clear architecture"],
            criteria_missing=["more metrics"],
            critique="Strong tradeoff framing.",
            improved_answer="Add SLO metrics.",
            follow_ups=[follow_up],
        ),
    )


def _print_step(n: int, user: str, assistant: str, *, scored: bool, pending: str | None) -> None:
    print(f"\n--- Step {n} ---")
    print(f"USER: {user}")
    print(f"ASSISTANT: {assistant[:500]}{'...' if len(assistant) > 500 else ''}")
    print(f"SCORED: {scored}")
    print(f"PENDING: {pending or '(none)'}")


def main() -> int:
    failures: list[str] = []
    session: dict = {"ia_usage_mode": "demo"}
    clear_mock_interview_runtime_state(session)
    messages: list[ChatMessage] = []

    question_queue = [
        f"1. {Q1}",
        f"1. {Q2}",
        f"1. {Q3}",
    ]
    q_idx = {"i": 0}

    def next_question(*_a, **_k):
        i = q_idx["i"]
        q_idx["i"] = min(i + 1, len(question_queue) - 1)
        return _question_result(question_queue[i])

    clarify_resp = LLMResponse(
        text=(
            "I mean an app that is observable, guarded against prompt injection, tested with "
            "fixtures, and deployable with clear failure modes—not just a demo notebook.\n\n"
            f"**Question:** {PENDING_AFTER_OFF_TOPIC}"
        ),
        model="gpt-4o-mini",
        usage=None,
        raw_response_id=None,
    )

    steps = [
        ("I am ready.", "start", False),
        ("Skip this question.", "skip", False),
        ("Ask me another question.", "next", False),
        ("What is the capital of France?", "off_topic_static", False),
        ("What is the Bitcoin price today?", "off_topic_live", False),
        (
            "Can you explain what you mean by production ready LLM application?",
            "clarify",
            False,
        ),
        (
            "I designed a Streamlit based AI interview preparation assistant using OpenAI, "
            "prompt strategies, CV parsing, guardrails, deterministic evaluation fixtures, "
            "GitHub Actions, and Streamlit Cloud deployment. The main tradeoff was keeping "
            "the app lightweight and easy to deploy while still adding reliability features "
            "such as retry handling, prompt injection checks, token usage visibility, and "
            "deterministic tests.",
            "answer",
            True,
        ),
    ]

    with patch(
        "interview_app.services.chat_service.run_input_pipeline",
        return_value=InputPipelineResult(ok=True),
    ):
        with patch(
            "interview_app.services.chat_service.generate_questions",
            side_effect=next_question,
        ):
            with patch(
                "interview_app.services.chat_service.evaluate_answer",
                return_value=_eval_result("How would you monitor token cost in production?"),
            ) as ev_mock:
                with patch(
                    "interview_app.services.chat_service.LLMClient"
                ) as llm_cls:
                    llm_cls.return_value.generate_response.return_value = clarify_resp

                    for n, (user_text, kind, expect_score) in enumerate(steps, start=1):
                        messages.append(ChatMessage(role="user", content=user_text))
                        before_ev = ev_mock.call_count
                        out = run_turn(_settings(), messages, session_state=session)
                        messages.append(
                            ChatMessage(role="assistant", content=out.assistant_message)
                        )
                        scored = ev_mock.call_count > before_ev
                        pending = session.get("ia_mock_pending_question")
                        _print_step(n, user_text, out.assistant_message, scored=scored, pending=pending)

                        if scored != expect_score:
                            failures.append(
                                f"Step {n} ({kind}): expected scored={expect_score}, got {scored}"
                            )

                        if kind == "skip":
                            if Q2 not in out.assistant_message:
                                failures.append(f"Step {n}: skip did not surface Q2")
                            if "Score" in out.assistant_message or "**Overall" in out.assistant_message:
                                failures.append(f"Step {n}: skip produced evaluation output")
                            if pending == Q1:
                                failures.append(f"Step {n}: pending still Q1 after skip")

                        if kind == "next":
                            if Q3 not in out.assistant_message:
                                failures.append(f"Step {n}: next did not surface Q3")
                            if pending == Q2:
                                failures.append(f"Step {n}: pending unchanged after next")

                        if kind == "off_topic_static":
                            if "Paris" not in out.assistant_message:
                                failures.append(f"Step {n}: missing Paris")
                            if PENDING_AFTER_OFF_TOPIC not in out.assistant_message:
                                failures.append(f"Step {n}: missing redirect to pending question")

                        if kind == "off_topic_live":
                            low = out.assistant_message.lower()
                            if "do not have live" not in low:
                                failures.append(f"Step {n}: missing live-data disclaimer")
                            if any(x in out.assistant_message for x in ("$", "USD", "42", "69")):
                                failures.append(f"Step {n}: possible price hallucination")

                        if kind == "clarify":
                            low = out.assistant_message.lower()
                            if not any(
                                w in low
                                for w in (
                                    "observable",
                                    "guard",
                                    "deploy",
                                    "failure",
                                    "production",
                                )
                            ):
                                failures.append(f"Step {n}: clarification missing explanation")
                            if out.assistant_message.count(PENDING_AFTER_OFF_TOPIC) < 1:
                                failures.append(f"Step {n}: clarification missing question restate")

                        if kind == "answer":
                            if out.evaluation is None:
                                failures.append(f"Step {n}: expected evaluation result")
                            if "Score" not in out.assistant_message:
                                failures.append(f"Step {n}: missing score in feedback")

    # Saved sessions: save, list, delete; verify layout source/CSS
    meta = SessionMeta(
        id="smoke-test",
        title="Smoke session",
        created_at="2026-06-09T12:00:00Z",
        role_category="Other",
        role_title="AI Engineer",
        seniority="Mid-Level",
        interview_round="Technical Interview",
        interview_focus="Technical Knowledge",
    )
    msgs = [m.model_dump(exclude_none=True) for m in messages]
    sid = save_session(None, meta, msgs, title="Smoke session", session_state=session)
    listed = list_sessions(session)
    if not any(s.get("id") == sid for s in listed):
        failures.append("Saved session not listed after save")
    delete_session(sid, session)

    controls = (ROOT / "src/interview_app/app/controls.py").read_text(encoding="utf-8")
    theme = (ROOT / "src/interview_app/ui/theme.py").read_text(encoding="utf-8")
    if '"Open session"' not in controls or '"Delete session"' not in controls:
        failures.append("Saved sessions buttons missing Open session/Delete session labels")
    if "ia-saved-session-card" not in controls or "white-space: nowrap" not in theme:
        failures.append("Saved sessions nowrap CSS/layout missing")

    print("\n=== Saved sessions UI ===")
    print("Save/list/delete: OK")
    print('Open session + Delete session labels present; ia-saved-session-card + white-space: nowrap in theme')

    print("\n=== SUMMARY ===")
    if failures:
        print("FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("All smoke checks PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
