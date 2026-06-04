"""
Strategy comparison UI: two-strategy selector, side-by-side results, optional evaluation.

Used by the Interview Questions tab only (Streamlit). No changes to prompt backends.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from interview_app.app.ui_settings import UISettings
from interview_app.storage.strategy_comparison_evaluations import append_evaluation
from interview_app.utils.interview_question_output import (
    parse_generation_questions_list,
    try_parse_questions_json,
)


def render_comparison_results(
    *,
    label_a: str,
    label_b: str,
    key_a: str,
    key_b: str,
    text_a: str,
    text_b: str,
    ok_a: bool,
    ok_b: bool,
    err_a: str,
    err_b: str,
) -> None:
    """Side-by-side aligned rows: Question 1 | Question 1, etc."""
    st.markdown("##### Results")

    if not ok_a and not ok_b:
        st.warning(err_a or err_b or "Both generations failed.")
        return

    qs_a = parse_generation_questions_list(text_a, key_a) if ok_a else []
    qs_b = parse_generation_questions_list(text_b, key_b) if ok_b else []

    # Header
    h1, h2 = st.columns(2, gap="medium")
    with h1:
        st.markdown(
            f'<div class="ia-compare-col-head"><span class="ia-compare-badge">A</span> {label_a}</div>',
            unsafe_allow_html=True,
        )
    with h2:
        st.markdown(
            f'<div class="ia-compare-col-head"><span class="ia-compare-badge">B</span> {label_b}</div>',
            unsafe_allow_html=True,
        )

    if not qs_a and ok_a and text_a.strip():
        qs_a = [text_a.strip()]
    if not qs_b and ok_b and text_b.strip():
        qs_b = [text_b.strip()]

    n = max(len(qs_a), len(qs_b), 1)
    for i in range(n):
        c1, c2 = st.columns(2, gap="medium")
        a_cell = qs_a[i] if i < len(qs_a) else ""
        b_cell = qs_b[i] if i < len(qs_b) else ""
        with c1:
            with st.container(border=True):
                st.caption(f"Question {i + 1}")
                if ok_a:
                    if a_cell:
                        st.markdown(a_cell)
                    else:
                        st.markdown("_—_")
                    _maybe_structured_caption(text_a, key_a, i)
                else:
                    st.error(err_a or "Failed.")
        with c2:
            with st.container(border=True):
                st.caption(f"Question {i + 1}")
                if ok_b:
                    if b_cell:
                        st.markdown(b_cell)
                    else:
                        st.markdown("_—_")
                    _maybe_structured_caption(text_b, key_b, i)
                else:
                    st.error(err_b or "Failed.")


def _maybe_structured_caption(full_text: str, strategy_key: str, index: int) -> None:
    if strategy_key != "structured_output":
        return
    parsed = try_parse_questions_json(full_text)
    if not parsed or index >= len(parsed):
        return
    item = parsed[index]
    bits = []
    if item.get("skill_tested"):
        bits.append(f"Skill: {item.get('skill_tested')}")
    if item.get("difficulty"):
        bits.append(f"Level: {item.get('difficulty')}")
    if item.get("why_it_matters"):
        bits.append(str(item.get("why_it_matters")))
    if bits:
        st.caption(" · ".join(bits))


def render_evaluation_section(
    *,
    settings: UISettings,
    key_a: str,
    key_b: str,
    label_a: str,
    label_b: str,
) -> None:
    """Sliders + winner + save to local JSON."""
    st.markdown("##### Evaluate the strategies")
    st.caption(
        "Rate this run and pick a winner. Saved locally under your app `data/` folder for your own review."
    )

    r1, r2, r3 = st.columns(3)
    with r1:
        realism = st.slider("Realism", 1, 5, 3, key="ia_cmp_eval_realism")
    with r2:
        difficulty = st.slider("Difficulty match", 1, 5, 3, key="ia_cmp_eval_difficulty")
    with r3:
        overall = st.slider("Overall quality", 1, 5, 3, key="ia_cmp_eval_overall")

    winner = st.radio(
        "Winner",
        options=["strategy_a", "strategy_b"],
        format_func=lambda x: label_a if x == "strategy_a" else label_b,
        horizontal=True,
        key="ia_cmp_eval_winner",
    )

    if st.button("Save evaluation", key="ia_cmp_eval_save", use_container_width=True):
        record: dict[str, Any] = {
            "role_title": settings.role_title,
            "role_category": settings.role_category,
            "interview_focus": settings.interview_focus,
            "strategy_a": key_a,
            "strategy_b": key_b,
            "label_a": label_a,
            "label_b": label_b,
            "realism": realism,
            "difficulty_match": difficulty,
            "overall_quality": overall,
            "winner": winner,
        }
        path = append_evaluation(record)
        st.success(f"Saved evaluation to `{path.name}`.")
        st.toast("Evaluation saved.")
