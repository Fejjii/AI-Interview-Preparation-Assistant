from __future__ import annotations

"""Fixture-driven checks: CV JSON shape and delimiter-breakout sanitization."""

import json

import pytest

from evaluations.checks import (
    check_cv_extraction_shape,
    check_cv_text_sanitized,
    load_fixture_cases,
)
from interview_app.cv.json_utils import parse_llm_json_model
from interview_app.cv.models import CVStructuredExtraction
from tests.evaluations.conftest import FIXTURES_DIR


def _cases() -> list[dict]:
    return load_fixture_cases(FIXTURES_DIR / "cv_extraction_cases.json")


@pytest.mark.parametrize("case", _cases(), ids=lambda c: c["id"])
def test_cv_extraction_from_fixture(case: dict) -> None:
    raw = json.dumps(case["mock_llm_json"])
    model = parse_llm_json_model(raw, CVStructuredExtraction)
    shape = check_cv_extraction_shape(
        model,
        require_profile=case.get("require_profile", True),
        require_skills=case.get("require_skills", True),
        min_skills=case.get("min_skills", 1),
    )
    assert shape.ok, shape.detail

    if case.get("strip_delimiters"):
        san = check_cv_text_sanitized(
            case["cv_text_snippet"],
            forbidden_substrings=case.get("forbidden_in_cleaned"),
        )
        assert san.ok, san.detail
