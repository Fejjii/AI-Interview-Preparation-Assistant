from __future__ import annotations

"""Fixture-driven checks: generated questions match role/focus, avoid off-topic themes."""

import pytest

from evaluations.checks import check_question_relevance, load_fixture_cases
from tests.evaluations.conftest import FIXTURES_DIR


def _cases() -> list[dict]:
    return load_fixture_cases(FIXTURES_DIR / "question_relevance_cases.json")


@pytest.mark.parametrize("case", _cases(), ids=lambda c: c["id"])
def test_question_relevance_from_fixture(case: dict) -> None:
    result = check_question_relevance(
        case["mocked_questions"],
        expected_focus_keywords=case["expected_focus_keywords"],
        disallowed_irrelevant_themes=case.get("disallowed_irrelevant_themes"),
        min_questions_with_hits=case.get("min_questions_with_hits", 1),
    )
    expect_pass = case.get("expect_pass", True)
    if expect_pass:
        assert result.ok, result.detail
    else:
        assert not result.ok, f"Expected failure but passed: {result.detail}"
