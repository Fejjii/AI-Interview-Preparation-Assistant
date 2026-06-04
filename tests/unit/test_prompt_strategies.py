from __future__ import annotations

"""
Unit tests for prompt strategies (`interview_app.prompts.prompt_strategies`).

Goal:
- verify each strategy returns non-empty system + user prompts
- sanity-check that the structured-output strategy actually asks for JSON
"""

from interview_app.prompts.prompt_strategies import (
    build_chain_of_thought_prompt,
    build_few_shot_prompt,
    build_role_based_prompt,
    build_structured_output_prompt,
    build_zero_shot_prompt,
)
from interview_app.prompts.prompt_templates import load_template_text


def test_template_text_strips_file_comment_header() -> None:
    """Model-facing template text must not include the `<!-- -->` file preamble."""
    txt = load_template_text("zero_shot")
    assert not txt.lstrip().startswith("<!--")
    assert "name: zero_shot" not in txt


def test_prompt_strategies_return_non_empty_prompts() -> None:
    """All strategies should return usable prompt strings."""
    common = {
        "role_category": "Software Engineering",
        "role_title": "Software Engineer",
        "seniority": "Senior",
        "interview_round": "Technical Interview",
        "interview_focus": "Technical Knowledge",
        "job_description": "Build APIs; collaborate with product; write tests.",
        "n_questions": 5,
    }

    results = [
        build_zero_shot_prompt(**common),
        build_few_shot_prompt(**common),
        build_chain_of_thought_prompt(**common),
        build_structured_output_prompt(**common),
        build_role_based_prompt(**common),
    ]

    for res in results:
        assert res.system_prompt.strip()
        assert res.user_prompt.strip()
        assert res.template_name


def test_structured_output_template_mentions_json() -> None:
    """Structured output strategy should request JSON (for easier parsing)."""
    res = build_structured_output_prompt(
        role_category="Software Engineering",
        role_title="Backend Engineer",
        seniority="Mid-Level",
        interview_round="System Design Interview",
        interview_focus="System Design / Architecture",
        job_description="Design scalable APIs.",
        n_questions=3,
    )
    assert "json" in res.user_prompt.lower()
    assert "skill_tested" in res.user_prompt
    assert "why_it_matters" in res.user_prompt


def test_zero_shot_omits_persona_calibration_in_system_prompt() -> None:
    """Zero-shot keeps system prompt minimal: technique + language, no persona calibration block."""
    res = build_zero_shot_prompt(
        role_category="Software Engineering",
        role_title="Backend Engineer",
        seniority="Senior",
        interview_round="Technical Interview",
        interview_focus="Technical Knowledge",
        n_questions=3,
        persona="Bar Raiser (Strict)",
    )
    assert "Interviewer tone" not in res.system_prompt
    assert "Bar Raiser" not in res.system_prompt


def test_few_shot_injects_focus_aligned_demonstrations() -> None:
    res = build_few_shot_prompt(
        role_category="Data Engineering",
        role_title="Analytics Engineer",
        seniority="Mid-Level",
        interview_round="Technical Interview",
        interview_focus="System Design / Architecture",
        n_questions=2,
    )
    assert "Demonstration context" in res.user_prompt
    assert "Example interview questions" in res.user_prompt
    up = res.user_prompt.lower()
    assert "warehouse" in up or "ingestion" in up or "near-real-time" in up or "streaming" in up


def test_role_based_includes_identity_and_behavior() -> None:
    res = build_role_based_prompt(
        role_category="Software Engineering",
        role_title="Senior Data Engineer",
        seniority="Senior",
        interview_round="Hiring Manager Interview",
        interview_focus="Leadership / Management",
        persona="Hiring Manager",
        n_questions=2,
    )
    assert "Senior Data Engineer" in res.user_prompt
    assert "conducting the" in res.user_prompt.lower() or "conducting" in res.user_prompt.lower()
    assert "outcome-focused" in res.user_prompt.lower() or "Hiring Manager" in res.user_prompt


def test_chain_of_thought_system_lists_internal_steps() -> None:
    res = build_chain_of_thought_prompt(
        role_category="Software Engineering",
        role_title="Engineer",
        seniority="Senior",
        interview_round="Technical Interview",
        interview_focus="Technical Knowledge",
        n_questions=3,
    )
    assert "chain-of-thought" in res.system_prompt.lower()
    assert "weak" in res.system_prompt.lower() and "strong" in res.system_prompt.lower()
    assert res.debug_trace is not None and res.debug_trace.cot_reasoning_scaffold_injected is True
