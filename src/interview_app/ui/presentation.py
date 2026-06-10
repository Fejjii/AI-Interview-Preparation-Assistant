"""Recruiter-facing UI presentation flags for the polished demo branch.

Centralizes what end users see vs. what stays available only in code/tests.
Core generation defaults and behavior are unchanged; this module gates chrome only.
"""

from __future__ import annotations


def show_advanced_sidebar_controls() -> bool:
    """Model tuning, prompt strategy, workspace shortcuts, developer notes."""
    return False


def show_technical_metadata() -> bool:
    """Usage lines, response metadata JSON, LLM debug expanders in main tabs."""
    return False


def show_strategy_comparison_by_default() -> bool:
    """Strategy A/B comparison block on Interview Questions tab."""
    return False


def allow_debug_prompts() -> bool:
    """Effective prompts / settings debug expanders (recruiter demo: always off)."""
    return False


def sanitize_recruiter_demo_session_state(session_state: dict) -> None:
    """
    Drop stale debug UI flags from older sessions (e.g. main-branch sidebar checkbox).

    Does not alter generation, guardrails, or saved session payloads.
    """
    if allow_debug_prompts():
        return
    session_state.pop("ia_show_debug", None)
