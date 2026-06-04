"""Deterministic evaluation helpers (no OpenAI calls).

These functions wrap production parsers/classifiers with transparent, keyword- and
shape-based checks suitable for fixture-driven regression tests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from interview_app.cv.models import CVStructuredExtraction
from interview_app.utils.types import EvaluationResult


@dataclass(frozen=True)
class CheckResult:
    """Outcome of a single evaluation check."""

    ok: bool
    detail: str = ""


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _contains_keyword(text: str, keyword: str) -> bool:
    k = (keyword or "").strip().lower()
    if not k:
        return False
    if " " in k:
        return k in _norm(text)
    return bool(re.search(rf"\b{re.escape(k)}\b", _norm(text))) or k in _norm(text)


def check_question_relevance(
    questions: list[str],
    *,
    expected_focus_keywords: list[str],
    disallowed_irrelevant_themes: list[str] | None = None,
    min_keyword_hits_per_question: int = 1,
    min_questions_with_hits: int = 1,
) -> CheckResult:
    """
    Verify mocked questions align with role/focus keywords and avoid off-topic themes.

    Protects against question generation drifting to unrelated domains (e.g. salary
    talk during a technical systems-design round).
    """
    qs = [q.strip() for q in questions if (q or "").strip()]
    if not qs:
        return CheckResult(ok=False, detail="No questions provided.")

    disallowed = disallowed_irrelevant_themes or []
    for q in qs:
        for theme in disallowed:
            if _contains_keyword(q, theme):
                return CheckResult(
                    ok=False,
                    detail=f"Disallowed theme '{theme}' found in question: {q[:80]}...",
                )

    keywords = [k for k in expected_focus_keywords if (k or "").strip()]
    if not keywords:
        return CheckResult(ok=True, detail="No expected keywords configured.")

    hits = 0
    for q in qs:
        count = sum(1 for k in keywords if _contains_keyword(q, k))
        if count >= min_keyword_hits_per_question:
            hits += 1

    if hits < min_questions_with_hits:
        return CheckResult(
            ok=False,
            detail=(
                f"Only {hits}/{len(qs)} questions met keyword threshold "
                f"(need {min_questions_with_hits} with >={min_keyword_hits_per_question} hits)."
            ),
        )
    return CheckResult(ok=True, detail=f"{hits}/{len(qs)} questions aligned with focus keywords.")


def check_evaluation_shape(
    evaluation: EvaluationResult | None,
    *,
    expect_valid: bool,
    expect_follow_up: bool = False,
    min_score: int | None = None,
) -> CheckResult:
    """
    Validate parsed answer-evaluation structure (score, lists, model answer, follow-ups).

    Protects the feedback tab and mock-interview flow from parser regressions when the
    model uses the expected markdown section headers.
    """
    if not expect_valid:
        if evaluation is None:
            return CheckResult(ok=True, detail="Parser returned None (safe empty fallback).")
        if evaluation.score == 0 and not evaluation.improved_answer and not evaluation.strengths:
            return CheckResult(ok=True, detail="Sparse fallback structure (no crash).")
        return CheckResult(
            ok=True,
            detail="Malformed input produced partial structure without raising.",
        )

    if evaluation is None:
        return CheckResult(
            ok=False, detail="Expected structured evaluation but parser returned None."
        )

    if min_score is not None and evaluation.score < min_score:
        return CheckResult(ok=False, detail=f"Score {evaluation.score} below minimum {min_score}.")

    if not evaluation.strengths:
        return CheckResult(ok=False, detail="Missing strengths section.")
    if not evaluation.improvements:
        return CheckResult(ok=False, detail="Missing improvements / gaps section.")
    if not (evaluation.improved_answer or "").strip():
        return CheckResult(ok=False, detail="Missing improved / model answer section.")

    if expect_follow_up:
        has_follow = bool((evaluation.next_follow_up_question or "").strip()) or bool(
            evaluation.follow_ups
        )
        if not has_follow:
            return CheckResult(ok=False, detail="Expected follow-up question or suggestions.")

    return CheckResult(ok=True, detail="Evaluation shape complete.")


def check_cv_extraction_shape(
    model: CVStructuredExtraction,
    *,
    require_profile: bool = True,
    require_skills: bool = True,
    require_experience: bool = False,
    require_projects: bool = False,
    min_skills: int = 1,
) -> CheckResult:
    """Validate CV structured extraction fields expected by the CV prep tab."""
    if require_profile and not (model.profile_summary or "").strip():
        return CheckResult(ok=False, detail="Missing profile_summary.")
    if require_skills and len(model.skills) < min_skills:
        return CheckResult(ok=False, detail=f"Expected at least {min_skills} skills.")
    if require_experience and not model.work_experience:
        return CheckResult(ok=False, detail="Missing work_experience entries.")
    if require_projects and not model.projects:
        return CheckResult(ok=False, detail="Missing projects entries.")
    return CheckResult(ok=True, detail="CV extraction shape valid.")


def check_cv_text_sanitized(
    cv_text: str, *, forbidden_substrings: list[str] | None = None
) -> CheckResult:
    """
    Confirm delimiter tokens were stripped from untrusted CV text before prompting.

    Protects against delimiter-breakout injection in the CV upload path.
    """
    from interview_app.cv.delimiters import CV_BEGIN, CV_END
    from interview_app.cv.text_cleaning import normalize_cv_text

    cleaned = normalize_cv_text(cv_text)
    if CV_BEGIN in cleaned or CV_END in cleaned:
        return CheckResult(ok=False, detail="CV delimiter tokens remain after normalization.")
    for sub in forbidden_substrings or ():
        if sub in cleaned:
            return CheckResult(ok=False, detail=f"Forbidden substring still present: {sub}")
    return CheckResult(ok=True, detail="CV text sanitized.")


def load_fixture_cases(path: Any, *, key: str = "cases") -> list[dict[str, Any]]:
    """Load a JSON fixture file and return the case list."""
    import json
    from pathlib import Path

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = data.get(key, data)
    if not isinstance(cases, list):
        raise ValueError(f"Fixture {path} must contain a list under '{key}'.")
    return cases
