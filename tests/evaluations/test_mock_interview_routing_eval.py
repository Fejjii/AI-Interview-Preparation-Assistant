from __future__ import annotations

"""Fixture-driven checks: mock interview turn routing without OpenAI."""

import pytest

from evaluations.checks import load_fixture_cases
from interview_app.services.mock_interview_flow import (
    MockInterviewTurnKind,
    UserTurnType,
    detect_mock_interview_turn_kind,
    detect_user_turn_type,
)
from tests.evaluations.conftest import FIXTURES_DIR


def _cases() -> list[dict]:
    return load_fixture_cases(FIXTURES_DIR / "mock_interview_routing_cases.json")


@pytest.mark.parametrize("case", _cases(), ids=lambda c: c["id"])
def test_mock_interview_routing_from_fixture(case: dict) -> None:
    pending = case.get("pending_question")
    kind = detect_mock_interview_turn_kind(case["message"], pending)
    expected_kind = MockInterviewTurnKind(case["expected_turn_kind"])
    assert kind == expected_kind, f"Got {kind.value}, expected {expected_kind.value}"

    if "expected_user_turn_type" in case:
        turn = detect_user_turn_type(case["message"], pending_question=pending)
        assert turn == UserTurnType(case["expected_user_turn_type"])
