"""Feedback / Evaluation workspace tab."""

import streamlit as st

from interview_app.app.interview_form_config import validate_role_title
from interview_app.app.tabs.shared import render_section_heading, session_openai_key
from interview_app.app.ui_settings import UISettings
from interview_app.services.answer_evaluator import evaluate_answer
from interview_app.ui.display import (
    show_error,
    show_evaluation_result,
    show_guardrail_summary,
    show_llm_response,
    show_prompt_debug,
    show_settings_debug,
)
from interview_app.ui.widgets import answer_input, question_context_input
from interview_app.utils.errors import safe_user_message
from interview_app.utils.language import DEFAULT_LANGUAGE, detect_language


def _render_answer_feedback_tab(settings: UISettings) -> None:
    """Paste question + answer; show structured evaluation."""
    render_section_heading(
        "Feedback / Evaluation",
        "Paste a question and your answer to get structured feedback and improvement tips.",
    )

    question = question_context_input()
    answer = answer_input()

    if st.button(
        "Evaluate answer",
        type="primary",
        use_container_width=True,
        key="btn_evaluate_answer",
    ):
        ok_title, _ = validate_role_title(settings.role_title)
        if not ok_title:
            st.warning("Set a **target role** in the sidebar.")
        else:
            if st.session_state.get("response_language") is None and (
                question.strip() or answer.strip()
            ):
                st.session_state.response_language = detect_language(question or answer)
            resolved_lang = st.session_state.get("response_language") or DEFAULT_LANGUAGE
            try:
                with st.spinner("Evaluating answer…"):
                    eval_result = evaluate_answer(
                        role_category=settings.role_category,
                        role_title=settings.role_title,
                        seniority=settings.seniority,
                        interview_round=settings.interview_round,
                        interview_focus=settings.interview_focus,
                        effective_difficulty=settings.effective_question_difficulty,
                        job_description=settings.job_description,
                        question=question,
                        answer=answer,
                        model=settings.model_preset,
                        temperature=settings.temperature,
                        top_p=settings.top_p,
                        max_tokens=settings.max_tokens,
                        response_language=resolved_lang,
                        persona=settings.persona,
                        session_state=dict(st.session_state),
                        openai_api_key=session_openai_key(),
                    )
            except Exception as exc:
                show_error(title="Evaluation failed", body=safe_user_message(exc))
            else:
                show_guardrail_summary(guardrails=eval_result.guardrails)
                if not eval_result.ok or eval_result.response is None:
                    show_error(
                        title="Request blocked",
                        body=eval_result.error or "Unknown error.",
                    )
                else:
                    if eval_result.evaluation:
                        show_evaluation_result(
                            eval_result.evaluation,
                            llm_response=eval_result.response,
                        )
                        st.toast("Evaluation complete.")
                    else:
                        show_llm_response(title="Evaluation", response=eval_result.response)
                    if (
                        settings.show_debug
                        and eval_result.system_prompt
                        and eval_result.user_prompt
                    ):
                        show_prompt_debug(
                            system_prompt=eval_result.system_prompt,
                            user_prompt=eval_result.user_prompt,
                        )

    if settings.show_debug:
        show_settings_debug(
            settings=settings,
            extra={"question_len": len(question), "answer_len": len(answer)},
        )
