"""
Constants and helpers for the interview preparation form.

Supports role categories, interview rounds, focus options, difficulty inference,
and conditional UX (technical vs non-technical job families).
"""

from __future__ import annotations

ROLE_CATEGORIES: tuple[str, ...] = (
    "Software Engineering",
    "Data Engineering",
    "Data Analysis",
    "AI / Machine Learning",
    "Product Management",
    "Business Analysis",
    "Consulting",
    "Cloud / DevOps",
    "Cybersecurity",
    "QA / Testing",
    "Design / UX",
    "Sales / Customer Success",
    "Finance",
    "HR / People Operations",
    "Marketing",
    "Operations",
    "Other",
)

# Categories where system-design-style questions are typically relevant.
SYSTEM_DESIGN_FOCUS_RELEVANT: frozenset[str] = frozenset(
    {
        "Software Engineering",
        "Data Engineering",
        "Data Analysis",
        "AI / Machine Learning",
        "Cloud / DevOps",
        "Cybersecurity",
    }
)

# Categories that benefit from prominent technical / architecture-style content.
TECHNICAL_CATEGORIES: frozenset[str] = frozenset(
    {
        "Software Engineering",
        "Data Engineering",
        "AI / Machine Learning",
        "Cloud / DevOps",
        "Cybersecurity",
    }
)

SENIORITY_OPTIONS: tuple[str, ...] = (
    "Entry-Level / Junior",
    "Mid-Level",
    "Senior",
    "Lead / Staff",
    "Principal / Architect",
    "Manager",
    "Director",
)

INTERVIEW_ROUNDS: tuple[str, ...] = (
    "Recruiter Screen",
    "Hiring Manager Interview",
    "Technical Interview",
    "Case Study Interview",
    "System Design Interview",
    "Behavioral Interview",
    "Final Interview",
    "Executive Interview",
)

# Full catalog; UI may filter or reorder based on role category and seniority.
INTERVIEW_FOCUS_OPTIONS: tuple[str, ...] = (
    "Behavioral / Soft Skills",
    "Technical Knowledge",
    "Coding / Practical Exercise",
    "System Design / Architecture",
    "Leadership / Management",
    "Culture Fit / Values",
    "CV / Experience Deep Dive",
    "Business Case / Strategy",
    "Stakeholder Management",
    "Salary / Negotiation Preparation",
)

DIFFICULTY_MODES: tuple[str, ...] = ("Auto", "Easy", "Medium", "Hard", "Expert")

# Main sidebar: manual difficulty or Auto (uses ``infer_difficulty_from_context``).
QUESTION_DIFFICULTY_SIDEBAR_MODES: tuple[str, ...] = ("Auto", "Easy", "Medium", "Hard")

# Ordered levels used for Auto inference and round-based bumps.
_DIFFICULTY_ORDER: tuple[str, ...] = ("Easy", "Medium", "Hard", "Expert")

# Rounds that should increase calibrated difficulty by one step when Auto is on.
ROUNDS_THAT_BUMP_DIFFICULTY: frozenset[str] = frozenset(
    {
        "System Design Interview",
        "Final Interview",
        "Executive Interview",
    }
)

ROLE_TITLE_PLACEHOLDERS: dict[str, str] = {
    "Software Engineering": "e.g. Backend Engineer, Frontend Engineer, Full Stack Engineer",
    "Data Engineering": "e.g. Data Engineer, Analytics Engineer, ETL Developer",
    "Data Analysis": "e.g. Data Analyst, BI Analyst, Reporting Analyst",
    "AI / Machine Learning": "e.g. AI Engineer, ML Engineer, Applied AI Consultant",
    "Product Management": "e.g. Product Manager, Senior PM, Technical PM",
    "Business Analysis": "e.g. Business Analyst, Senior Business Analyst, BI Analyst",
    "Consulting": "e.g. Consultant, Senior Consultant, AI Consultant",
    "Cloud / DevOps": "e.g. DevOps Engineer, Cloud Engineer, SRE",
    "Cybersecurity": "e.g. Security Engineer, AppSec Engineer, SOC Analyst",
    "QA / Testing": "e.g. QA Engineer, SDET, Test Automation Engineer",
    "Design / UX": "e.g. Product Designer, UX Designer, UX Researcher",
    "Sales / Customer Success": "e.g. Account Executive, CSM, Solutions Consultant",
    "Finance": "e.g. Financial Analyst, FP&A Analyst",
    "HR / People Operations": "e.g. HR Business Partner, People Partner",
    "Marketing": "e.g. Growth Marketing Manager, Product Marketing Manager",
    "Operations": "e.g. Operations Manager, Program Manager",
    "Other": "e.g. your target role title",
}


def role_title_placeholder(role_category: str) -> str:
    """Dynamic placeholder for the role title field."""
    return ROLE_TITLE_PLACEHOLDERS.get(role_category, ROLE_TITLE_PLACEHOLDERS["Other"])


def default_focus_for_round(interview_round: str) -> str:
    """Suggested interview focus when the user selects a given round."""
    mapping: dict[str, str] = {
        "Recruiter Screen": "Behavioral / Soft Skills",
        "Hiring Manager Interview": "CV / Experience Deep Dive",
        "Technical Interview": "Technical Knowledge",
        "Case Study Interview": "Business Case / Strategy",
        "System Design Interview": "System Design / Architecture",
        "Behavioral Interview": "Behavioral / Soft Skills",
        "Final Interview": "Culture Fit / Values",
        "Executive Interview": "Leadership / Management",
    }
    return mapping.get(interview_round, "Behavioral / Soft Skills")


def default_persona_for_round(interview_round: str, *, persona_keys: tuple[str, ...]) -> str:
    """Suggested interviewer persona for a given round."""
    mapping: dict[str, str] = {
        "Recruiter Screen": "HR Recruiter",
        "Hiring Manager Interview": "Hiring Manager",
        "Technical Interview": "Technical Interviewer",
        "Case Study Interview": "Case Study Interviewer",
        "System Design Interview": "System Design Interviewer",
        "Behavioral Interview": "Friendly Interviewer",
        "Final Interview": "Hiring Manager",
        "Executive Interview": "Bar Raiser (Strict)",
    }
    key = mapping.get(interview_round, "Hiring Manager")
    return key if key in persona_keys else persona_keys[1]


def include_system_design_focus(role_category: str) -> bool:
    """Whether to offer System Design / Architecture in the focus list."""
    return role_category in SYSTEM_DESIGN_FOCUS_RELEVANT


def build_focus_options(
    role_category: str,
    seniority: str,
) -> list[str]:
    """
    Build ordered focus options: deprioritize system design for non-relevant
    categories; prioritize leadership and stakeholder topics for senior leaders.
    """
    opts = list(INTERVIEW_FOCUS_OPTIONS)
    if not include_system_design_focus(role_category):
        opts = [o for o in opts if o != "System Design / Architecture"]

    leadership_first = {"Manager", "Director"}
    if seniority in leadership_first:
        priority = [
            "Leadership / Management",
            "Stakeholder Management",
            "Behavioral / Soft Skills",
            "Culture Fit / Values",
            "CV / Experience Deep Dive",
        ]
        rest = [o for o in opts if o not in priority]
        opts = [o for o in priority if o in opts] + rest

    return opts


def infer_difficulty_from_context(
    *,
    seniority: str,
    interview_round: str,
    manual_mode: str,
) -> str:
    """
    Resolve effective difficulty for prompts.

    If manual_mode is not Auto, return manual_mode (Easy..Expert).
    Otherwise infer from seniority, then optionally bump for demanding rounds.
    """
    if manual_mode != "Auto":
        return manual_mode

    base_map: dict[str, str] = {
        "Entry-Level / Junior": "Easy",
        "Mid-Level": "Medium",
        "Senior": "Medium",
        "Lead / Staff": "Hard",
        "Principal / Architect": "Expert",
        "Manager": "Hard",
        "Director": "Expert",
    }
    level = base_map.get(seniority, "Medium")

    if interview_round in ROUNDS_THAT_BUMP_DIFFICULTY:
        level = _bump_difficulty(level)

    return level


def _bump_difficulty(level: str) -> str:
    """Raise difficulty by one step within Easy..Expert."""
    if level not in _DIFFICULTY_ORDER:
        return level
    idx = _DIFFICULTY_ORDER.index(level)
    return _DIFFICULTY_ORDER[min(idx + 1, len(_DIFFICULTY_ORDER) - 1)]


def validate_role_title(raw: str) -> tuple[bool, str]:
    """Return (ok, trimmed). Empty after trim is invalid."""
    t = (raw or "").strip()
    return (bool(t), t)


def truncate_job_description(text: str, max_chars: int = 8000) -> str:
    """Trim and cap job description length for pipelines."""
    return (text or "").strip()[:max_chars]
