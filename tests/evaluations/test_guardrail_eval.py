from __future__ import annotations

"""Fixture-driven checks: security guardrails allow legitimate prep, block attacks."""

import pytest

from evaluations.checks import load_fixture_cases
from interview_app.security.guards import detect_prompt_injection, run_guardrails
from tests.evaluations.conftest import FIXTURES_DIR


def _cases() -> list[dict]:
    return load_fixture_cases(FIXTURES_DIR / "guardrail_cases.json")


@pytest.mark.parametrize("case", _cases(), ids=lambda c: c["id"])
def test_guardrail_verdict_from_fixture(case: dict) -> None:
    # Strict-mode cases use explicit probe flag; others exercise the full guardrail wrapper.
    if "strict" in case:
        blocked = detect_prompt_injection(case["text"], strict=case["strict"])
        if case["expect_allow"]:
            assert blocked is False
        else:
            assert blocked is True
        return

    res = run_guardrails(case["text"], service="eval_guardrail")
    if case["expect_allow"]:
        assert res.ok is True, res.reason or res.flags
        assert res.injection_detected is False
    else:
        assert res.ok is False
        assert res.injection_detected is True
