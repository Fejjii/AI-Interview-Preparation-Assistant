from __future__ import annotations

"""Fixture-driven checks: answer feedback parser shape and safe handling of bad output."""

import pytest

from evaluations.checks import check_evaluation_shape, load_fixture_cases
from interview_app.services.answer_evaluator import _parse_evaluation_response
from tests.evaluations.conftest import FIXTURES_DIR


def _cases() -> list[dict]:
    return load_fixture_cases(FIXTURES_DIR / "answer_evaluation_cases.json")


@pytest.mark.parametrize("case", _cases(), ids=lambda c: c["id"])
def test_answer_evaluation_shape_from_fixture(case: dict) -> None:
    # Uses production markdown parser; no live OpenAI call.
    parsed = _parse_evaluation_response(case["mock_llm_output"])
    result = check_evaluation_shape(
        parsed,
        expect_valid=case["expect_valid"],
        expect_follow_up=case.get("expect_follow_up", False),
        min_score=case.get("min_score"),
    )
    assert result.ok, result.detail
