"""Tests that zero-shot, few-shot, and CoT prompts are structurally distinct and config-grounded."""

from __future__ import annotations

from interview_app.prompts.prompt_strategies import (
    build_chain_of_thought_prompt,
    build_few_shot_prompt,
    build_zero_shot_prompt,
)
from interview_app.services import interview_generator


def _common_kwargs() -> dict[str, object]:
    return {
        "role_category": "Data Engineering",
        "role_title": "Senior Data Engineer",
        "seniority": "Senior",
        "interview_round": "Technical Interview",
        "interview_focus": "Technical Knowledge",
        "job_description": "Own batch and streaming pipelines; Snowflake; dbt; Airflow.",
        "n_questions": 5,
        "response_language": "en",
        "difficulty": "Hard",
        "persona": "Hiring Manager",
    }


def test_strategy_prompts_are_substantially_different() -> None:
    """Same config must yield non-overlapping instruction DNA across strategies."""
    c = _common_kwargs()
    z = build_zero_shot_prompt(**c)
    f = build_few_shot_prompt(**c)
    t = build_chain_of_thought_prompt(**c)

    assert len({z.system_prompt, f.system_prompt, t.system_prompt}) == 3
    assert len({z.user_prompt, f.user_prompt, t.user_prompt}) == 3

    # Few-shot must carry exemplar pack + domain trace in body
    assert "Exemplars" in f.user_prompt or "exemplar" in f.user_prompt.lower()
    assert (
        "data_eng" in f.user_prompt or "ETL" in f.user_prompt or "pipeline" in f.user_prompt.lower()
    )

    # Zero-shot must not inject few-shot exemplar headings
    assert "Example interview questions" not in z.user_prompt
    assert "data_eng" not in z.user_prompt  # domain pack line is few-shot only

    # CoT system embeds the private reasoning scaffold
    assert "weak" in t.system_prompt.lower() and "strong" in t.system_prompt.lower()
    assert "trade-off" in t.system_prompt.lower() or "trade-offs" in t.system_prompt.lower()


def test_few_shot_more_scenario_forward_than_zero_shot() -> None:
    """Few-shot user instructions emphasize live scenarios vs baseline zero-shot."""
    c = _common_kwargs()
    z = build_zero_shot_prompt(**c)
    f = build_few_shot_prompt(**c)
    assert len(f.user_prompt) > len(z.user_prompt) + 400
    assert "scenario" in f.user_prompt.lower()
    assert "classic interview" in z.user_prompt.lower() or "standard" in z.user_prompt.lower()


def test_chain_of_thought_user_demands_depth_vs_zero_shot() -> None:
    """CoT user message should push situational / trade-off framing more than zero-shot."""
    c = _common_kwargs()
    z = build_zero_shot_prompt(**c)
    t = build_chain_of_thought_prompt(**c)
    z_lower = z.user_prompt.lower()
    t_lower = t.user_prompt.lower()
    # Zero-shot explicitly discourages elaborate case studies
    assert "multi-paragraph" in z_lower or "elaborate" in z_lower
    # CoT asks for deeper situational prompts
    assert "trade-off" in t_lower or "prioritization" in t_lower or "situational" in t_lower


def test_interview_generator_same_dispatch_for_all_strategies() -> None:
    """Single generation and comparison both go through `_build_prompt`."""
    common = {
        "role_category": "Software Engineering",
        "role_title": "Backend Engineer",
        "seniority": "Mid-Level",
        "interview_round": "Technical Interview",
        "interview_focus": "Technical Knowledge",
        "job_description": "APIs",
        "n_questions": 3,
        "response_language": "en",
        "difficulty": "Medium",
        "persona": "Hiring Manager",
    }
    pz = interview_generator._build_prompt(prompt_strategy="zero_shot", **common)
    pf = interview_generator._build_prompt(prompt_strategy="few_shot", **common)
    pc = interview_generator._build_prompt(prompt_strategy="chain_of_thought", **common)
    assert pz.template_name == "zero_shot" and pf.template_name == "few_shot"
    assert pc.template_name == "chain_of_thought"
    assert pz.system_prompt != pf.system_prompt
    assert pf.debug_trace is not None and pf.debug_trace.few_shot_example_count is not None
    assert pf.debug_trace.few_shot_example_count >= 2
    assert pc.debug_trace is not None and pc.debug_trace.cot_reasoning_scaffold_injected is True


def test_config_grounding_preserved_across_strategies() -> None:
    """Role, seniority, focus, JD snippets must appear in user prompts."""
    c = _common_kwargs()
    for build in (build_zero_shot_prompt, build_few_shot_prompt, build_chain_of_thought_prompt):
        res = build(**c)
        assert "Senior Data Engineer" in res.user_prompt
        assert "Data Engineering" in res.user_prompt
        assert "Technical Interview" in res.user_prompt
        assert "Technical Knowledge" in res.user_prompt
        assert "Snowflake" in res.user_prompt


def test_debug_traces_are_safe_and_actionable() -> None:
    for build in (build_zero_shot_prompt, build_few_shot_prompt, build_chain_of_thought_prompt):
        res = build(**_common_kwargs())
        assert res.debug_trace is not None
        d = res.debug_trace.as_dict()
        assert d["strategy_key"]
        assert d["template_name"]
        assert d["seniority_band"] == "senior"
        if d["strategy_key"] == "few_shot":
            assert d["few_shot_example_count"] is not None and int(d["few_shot_example_count"]) >= 2
            assert d["few_shot_domain"] == "data_eng"
