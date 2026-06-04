"""Composable prompt strategies for interview question generation (zero/few-shot, CoT, etc.).

Pure functions: no Streamlit imports, no network I/O. Each ``build_*`` function
returns ``PromptBuildResult`` (system + user strings) using templates from
``prompt_templates`` and persona text from ``personas``.

Consumed exclusively by ``services/interview_generator`` and unit tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from interview_app.prompts.few_shot_examples import (
    build_few_shot_demonstration_block,
    few_shot_trace_for_debug,
)
from interview_app.prompts.personas import get_persona_prompt
from interview_app.prompts.prompt_templates import load_template_text
from interview_app.prompts.question_prompt_helpers import (
    cot_reasoning_scaffold_system_text,
    diversity_block_chain_of_thought,
    diversity_block_few_shot,
    diversity_block_zero_shot,
    seniority_band,
    seniority_calibration_for_questions,
)
from interview_app.utils.language import language_instruction


@dataclass(frozen=True)
class PromptStrategyDebugTrace:
    """Opt-in diagnostics: which strategy path and exemplars were used (no secrets)."""

    strategy_key: str
    template_name: str
    seniority_band: str
    few_shot_domain: str | None
    few_shot_focus_resolved: str | None
    few_shot_example_count: int | None
    cot_reasoning_scaffold_injected: bool
    diversity_block_kind: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "strategy_key": self.strategy_key,
            "template_name": self.template_name,
            "seniority_band": self.seniority_band,
            "few_shot_domain": self.few_shot_domain,
            "few_shot_focus_resolved": self.few_shot_focus_resolved,
            "few_shot_example_count": self.few_shot_example_count,
            "cot_reasoning_scaffold_injected": self.cot_reasoning_scaffold_injected,
            "diversity_block_kind": self.diversity_block_kind,
        }


@dataclass(frozen=True)
class PromptBuildResult:
    """A fully-built prompt ready to send to `LLMClient`."""

    system_prompt: str
    user_prompt: str
    template_name: str
    debug_trace: PromptStrategyDebugTrace | None = None


def build_zero_shot_prompt(
    *,
    role_category: str,
    role_title: str,
    seniority: str,
    interview_round: str,
    interview_focus: str,
    job_description: str = "",
    n_questions: int = 5,
    response_language: str = "en",
    difficulty: str = "Medium",
    persona: str = "Hiring Manager",
) -> PromptBuildResult:
    """Build a direct, instruction-only (zero-shot) prompt."""
    template = load_template_text("zero_shot")
    diversity = diversity_block_zero_shot(n_questions=n_questions, seniority=seniority)
    seniority_calibration_block = seniority_calibration_for_questions(
        seniority=seniority, role_category=role_category
    )
    user_prompt = _format_template(
        template,
        role_category=role_category,
        role_title=role_title,
        seniority=seniority,
        interview_round=interview_round,
        interview_focus=interview_focus,
        job_description=_normalize_block(job_description),
        n_questions=n_questions,
        difficulty=difficulty,
        persona=persona,
        seniority_calibration_block=seniority_calibration_block,
        diversity_and_quality_block=diversity,
    )
    system_prompt = _system_prompt_for(
        "zero_shot",
        response_language=response_language,
        persona=persona,
        include_persona=False,
        seniority=seniority,
    )
    trace = PromptStrategyDebugTrace(
        strategy_key="zero_shot",
        template_name="zero_shot",
        seniority_band=seniority_band(seniority),
        few_shot_domain=None,
        few_shot_focus_resolved=None,
        few_shot_example_count=None,
        cot_reasoning_scaffold_injected=False,
        diversity_block_kind="zero_shot",
    )
    return PromptBuildResult(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        template_name="zero_shot",
        debug_trace=trace,
    )


def build_few_shot_prompt(
    *,
    role_category: str,
    role_title: str,
    seniority: str,
    interview_round: str,
    interview_focus: str,
    job_description: str = "",
    n_questions: int = 5,
    response_language: str = "en",
    difficulty: str = "Medium",
    persona: str = "Hiring Manager",
) -> PromptBuildResult:
    """Build a prompt that includes examples (few-shot) to steer format/quality."""
    template = load_template_text("few_shot")
    few_shot_demonstrations = build_few_shot_demonstration_block(
        role_category=role_category,
        role_title=role_title,
        seniority=seniority,
        interview_round=interview_round,
        interview_focus=interview_focus,
    )
    fs_meta = few_shot_trace_for_debug(
        role_category=role_category,
        role_title=role_title,
        seniority=seniority,
        interview_round=interview_round,
        interview_focus=interview_focus,
    )
    diversity = diversity_block_few_shot(n_questions=n_questions, seniority=seniority)
    seniority_calibration_block = seniority_calibration_for_questions(
        seniority=seniority, role_category=role_category
    )
    user_prompt = _format_template(
        template,
        role_category=role_category,
        role_title=role_title,
        seniority=seniority,
        interview_round=interview_round,
        interview_focus=interview_focus,
        job_description=_normalize_block(job_description),
        n_questions=n_questions,
        difficulty=difficulty,
        persona=persona,
        few_shot_demonstrations=few_shot_demonstrations,
        seniority_calibration_block=seniority_calibration_block,
        diversity_and_quality_block=diversity,
    )
    system_prompt = _system_prompt_for(
        "few_shot", response_language=response_language, persona=persona, seniority=seniority
    )
    trace = PromptStrategyDebugTrace(
        strategy_key="few_shot",
        template_name="few_shot",
        seniority_band=seniority_band(seniority),
        few_shot_domain=str(fs_meta["few_shot_domain"]),
        few_shot_focus_resolved=str(fs_meta["few_shot_focus_resolved"]),
        few_shot_example_count=int(fs_meta["few_shot_example_count"]),
        cot_reasoning_scaffold_injected=False,
        diversity_block_kind="few_shot",
    )
    return PromptBuildResult(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        template_name="few_shot",
        debug_trace=trace,
    )


def build_chain_of_thought_prompt(
    *,
    role_category: str,
    role_title: str,
    seniority: str,
    interview_round: str,
    interview_focus: str,
    job_description: str = "",
    n_questions: int = 5,
    response_language: str = "en",
    difficulty: str = "Medium",
    persona: str = "Hiring Manager",
) -> PromptBuildResult:
    """
    Build a prompt that encourages step-by-step reasoning.

    Note: The system prompt explicitly instructs the model not to reveal hidden reasoning.
    """
    template = load_template_text("chain_of_thought")
    diversity = diversity_block_chain_of_thought(n_questions=n_questions, seniority=seniority)
    seniority_calibration_block = seniority_calibration_for_questions(
        seniority=seniority, role_category=role_category
    )
    user_prompt = _format_template(
        template,
        role_category=role_category,
        role_title=role_title,
        seniority=seniority,
        interview_round=interview_round,
        interview_focus=interview_focus,
        job_description=_normalize_block(job_description),
        n_questions=n_questions,
        difficulty=difficulty,
        persona=persona,
        seniority_calibration_block=seniority_calibration_block,
        diversity_and_quality_block=diversity,
    )
    system_prompt = _system_prompt_for(
        "chain_of_thought",
        response_language=response_language,
        persona=persona,
        seniority=seniority,
    )
    trace = PromptStrategyDebugTrace(
        strategy_key="chain_of_thought",
        template_name="chain_of_thought",
        seniority_band=seniority_band(seniority),
        few_shot_domain=None,
        few_shot_focus_resolved=None,
        few_shot_example_count=None,
        cot_reasoning_scaffold_injected=True,
        diversity_block_kind="chain_of_thought",
    )
    return PromptBuildResult(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        template_name="chain_of_thought",
        debug_trace=trace,
    )


def build_structured_output_prompt(
    *,
    role_category: str,
    role_title: str,
    seniority: str,
    interview_round: str,
    interview_focus: str,
    job_description: str = "",
    n_questions: int = 5,
    response_language: str = "en",
    difficulty: str = "Medium",
    persona: str = "Hiring Manager",
) -> PromptBuildResult:
    """Build a prompt that asks for machine-readable output (JSON)."""
    template = load_template_text("structured_output")
    seniority_calibration_block = seniority_calibration_for_questions(
        seniority=seniority, role_category=role_category
    )
    user_prompt = _format_template(
        template,
        role_category=role_category,
        role_title=role_title,
        seniority=seniority,
        interview_round=interview_round,
        interview_focus=interview_focus,
        job_description=_normalize_block(job_description),
        n_questions=n_questions,
        difficulty=difficulty,
        persona=persona,
        seniority_calibration_block=seniority_calibration_block,
    )
    system_prompt = _system_prompt_for(
        "structured_output",
        response_language=response_language,
        persona=persona,
        seniority=seniority,
    )
    trace = PromptStrategyDebugTrace(
        strategy_key="structured_output",
        template_name="structured_output",
        seniority_band=seniority_band(seniority),
        few_shot_domain=None,
        few_shot_focus_resolved=None,
        few_shot_example_count=None,
        cot_reasoning_scaffold_injected=False,
        diversity_block_kind="n/a_structured",
    )
    return PromptBuildResult(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        template_name="structured_output",
        debug_trace=trace,
    )


def build_role_based_prompt(
    *,
    role_category: str,
    role_title: str,
    seniority: str,
    interview_round: str,
    interview_focus: str,
    job_description: str = "",
    n_questions: int = 5,
    response_language: str = "en",
    difficulty: str = "Medium",
    persona: str = "Hiring Manager",
) -> PromptBuildResult:
    """Build a prompt that sets a strong interviewer persona (role-based prompting)."""
    template = load_template_text("role_based")
    persona_identity = _role_based_identity_line(
        persona=persona,
        role_title=role_title,
        seniority=seniority,
        interview_round=interview_round,
        interview_focus=interview_focus,
    )
    persona_behavior = get_persona_prompt(persona)
    seniority_calibration_block = seniority_calibration_for_questions(
        seniority=seniority, role_category=role_category
    )
    user_prompt = _format_template(
        template,
        role_category=role_category,
        role_title=role_title,
        seniority=seniority,
        interview_round=interview_round,
        interview_focus=interview_focus,
        job_description=_normalize_block(job_description),
        n_questions=n_questions,
        difficulty=difficulty,
        persona=persona,
        persona_identity=persona_identity,
        persona_behavior=persona_behavior,
        seniority_calibration_block=seniority_calibration_block,
    )
    system_prompt = _system_prompt_for(
        "role_based", response_language=response_language, persona=persona, seniority=seniority
    )
    trace = PromptStrategyDebugTrace(
        strategy_key="role_based",
        template_name="role_based",
        seniority_band=seniority_band(seniority),
        few_shot_domain=None,
        few_shot_focus_resolved=None,
        few_shot_example_count=None,
        cot_reasoning_scaffold_injected=False,
        diversity_block_kind="n/a_role_based",
    )
    return PromptBuildResult(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        template_name="role_based",
        debug_trace=trace,
    )


def _role_based_identity_line(
    *,
    persona: str,
    role_title: str,
    seniority: str,
    interview_round: str,
    interview_focus: str,
) -> str:
    """Strong interviewer anchor for role-based prompting (user prompt body)."""
    return (
        f"You are **{persona}** conducting the **{interview_round}** for a candidate "
        f"targeting **{role_title}** ({seniority}). "
        f"This round should stress **{interview_focus}**. "
        "Stay in character: your questions should sound like a real interviewer, not a study guide."
    )


def _system_prompt_for(
    strategy: str,
    *,
    response_language: str = "en",
    persona: str = "Hiring Manager",
    include_persona: bool = True,
    seniority: str = "",
) -> str:
    """
    Return a distinct system prompt per technique.
    Appends persona tone (except zero-shot) and language instruction.
    """

    legacy_base = (
        "You are an AI interview assistant helping a candidate prepare for a realistic hiring "
        "conversation. Follow instructions precisely, stay role-relevant, and avoid inventing "
        "employer-specific facts that were not provided."
    )

    zero_base = (
        "You are a **technical interview coach** emulating a concise hiring interviewer. "
        "Produce only what the user asks for: clear, standard interview questions grounded in "
        "the supplied role, seniority, and focus—no hidden reasoning and no fabricated employer facts."
    )

    few_base = (
        "You are a **technical interviewer**. The user message contains **exemplar questions**—treat them as "
        "benchmarks for **realism, specificity, and interviewer voice**. Your job is to write **new** questions "
        "that could plausibly follow in the same interview, not to echo the exemplars."
    )

    cot_base = (
        "You are a **senior technical interviewer** who asks discriminating, production-aware questions. "
        "You prioritize scenarios that reveal prioritization, trade-offs, reliability, and judgment—not "
        "textbook recitation."
    )

    match strategy:
        case "zero_shot":
            base = zero_base
            tech = (
                "Technique: **Zero-shot**. The user message has **no** worked examples. Reply with **only** the "
                "numbered questions—no commentary, no plan, no “let me think aloud”. Honor **Seniority calibration** "
                "in the user message strictly."
            )
        case "few_shot":
            base = few_base
            tech = (
                "Technique: **Few-shot**. Internalize the exemplars’ **structure** (scenario richness, interviewer "
                "cadence). Generate **original** questions; superficially rewording an exemplar is not acceptable. "
                "Final difficulty must match **Seniority calibration**, not copy exemplar band by default."
            )
        case "chain_of_thought":
            base = cot_base
            tech = (
                f"{cot_reasoning_scaffold_system_text(seniority)}\n\n"
                "Technique: **Chain-of-thought (internal only)**. Complete the private checklist above, then output "
                "**only** the final numbered questions. Visible output must not contain reasoning fragments."
            )
        case "structured_output":
            base = legacy_base
            tech = (
                "Technique: Structured output. Return **valid JSON only**, exactly matching the schema "
                "in the user message. No markdown fences, no prose before or after the JSON."
            )
        case "role_based":
            base = legacy_base
            tech = (
                "Technique: Role-based prompting. The user message defines a concrete interviewer "
                "identity and behavior—honor it consistently in every line you output."
            )
        case _:
            base = legacy_base
            tech = ""

    prompt = f"{base}\n\n{tech}" if tech else base
    if include_persona:
        persona_fragment = get_persona_prompt(persona)
        prompt = f"{prompt}\n\nInterviewer tone (calibration): {persona_fragment}"
    return f"{prompt}\n\n{language_instruction(response_language)}"


def _normalize_block(text: str) -> str:
    """Normalize optional multi-line blocks so templates can assume a value exists."""
    t = (text or "").strip()
    return t if t else "(none)"


def _format_template(template: str, **kwargs: object) -> str:
    return template.format(**kwargs)


def evaluation_coaching_directive(prompt_strategy: str) -> str:
    """
    Brief instruction aligned with the active prompt strategy for mock-interview evaluation.

    Used only in mock interview (answer feedback tab keeps its own fixed coach prompt).
    """
    key = (
        prompt_strategy
        if prompt_strategy
        in {
            "zero_shot",
            "few_shot",
            "chain_of_thought",
            "structured_output",
            "role_based",
        }
        else "zero_shot"
    )
    directives: dict[str, str] = {
        "zero_shot": (
            "Coaching style: zero-shot — be direct, structured, and concise; avoid lengthy preamble."
        ),
        "few_shot": (
            "Coaching style: few-shot — anchor feedback to concrete patterns and short illustrative examples."
        ),
        "chain_of_thought": (
            "Coaching style: chain-of-thought — reason privately about gaps vs. role expectations, "
            "then output only the required sectioned feedback (no visible chain-of-thought)."
        ),
        "structured_output": (
            "Coaching style: structured output — keep section headers exactly as requested; "
            "prefer scannable bullets over prose walls."
        ),
        "role_based": (
            "Coaching style: role-based — stay consistent with the interviewer persona and hiring context."
        ),
    }
    return directives[key]
