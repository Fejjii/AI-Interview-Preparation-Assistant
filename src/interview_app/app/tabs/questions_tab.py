"""Interview Questions workspace tab (generation and strategy comparison)."""

import streamlit as st

from interview_app.app.interview_form_config import validate_role_title
from interview_app.app.tabs.shared import render_section_heading, session_openai_key
from interview_app.app.ui_settings import (
    PROMPT_STRATEGY_OPTIONS,
    UISettings,
    prompt_strategy_key_from_label,
)
from interview_app.services.interview_generator import generate_questions_from_settings
from interview_app.ui.display import (
    show_error,
    show_guardrail_summary,
    show_llm_response,
    show_prompt_debug,
    show_settings_debug,
)
from interview_app.ui.strategy_comparison import (
    render_comparison_results,
    render_evaluation_section,
)
from interview_app.utils.errors import safe_user_message
from interview_app.utils.language import DEFAULT_LANGUAGE, detect_language


def _maybe_run_pending_generation(settings: UISettings) -> None:
    """Run question generation once after sidebar shortcut."""
    if not st.session_state.get("ia_pending_generate"):
        return
    st.session_state.ia_pending_generate = False

    ok_title, _ = validate_role_title(settings.role_title)
    if not ok_title:
        st.warning("Set a **target role** in the sidebar to generate questions.")
        return

    jd = settings.job_description or ""
    if st.session_state.get("response_language") is None and jd.strip():
        st.session_state.response_language = detect_language(jd)
    resolved_lang = st.session_state.get("response_language") or DEFAULT_LANGUAGE
    n_questions = int(st.session_state.get("ia_n_questions", 5))

    try:
        with st.spinner("Generating questions…"):
            gen_result = generate_questions_from_settings(
                settings=settings,
                prompt_strategy=settings.prompt_strategy,
                n_questions=n_questions,
                session_state=dict(st.session_state),
                response_language=resolved_lang,
                openai_api_key=session_openai_key(),
            )
    except Exception as exc:
        show_error(title="Generation failed", body=safe_user_message(exc))
        return

    show_guardrail_summary(guardrails=gen_result.guardrails)
    if not gen_result.ok or gen_result.response is None:
        show_error(
            title="Request blocked",
            body=gen_result.error or "Unknown error.",
        )
        return

    show_llm_response(
        title="Generated questions",
        response=gen_result.response,
        settings=settings,
        structured=True,
    )
    st.toast("Questions generated.")
    if settings.show_debug and gen_result.prompt is not None:
        _tr = (
            gen_result.prompt.debug_trace.as_dict()
            if gen_result.prompt.debug_trace is not None
            else None
        )
        show_prompt_debug(
            system_prompt=gen_result.prompt.system_prompt,
            user_prompt=gen_result.prompt.user_prompt,
            strategy_trace=_tr,
        )


def _render_strategy_comparison_block(settings: UISettings) -> None:
    """Optional A/B strategy comparison (collapsed by default on recruiter demo)."""
    _strategy_labels = [lbl for lbl, _ in PROMPT_STRATEGY_OPTIONS]
    with st.container(border=True):
        st.caption("Compare two prompting approaches side by side.")
        sc1, sc2 = st.columns(2)
        with sc1:
            st.selectbox(
                "Approach A",
                options=_strategy_labels,
                index=0,
                key="ia_compare_sel_a",
            )
        with sc2:
            st.selectbox(
                "Approach B",
                options=_strategy_labels,
                index=min(1, len(_strategy_labels) - 1),
                key="ia_compare_sel_b",
            )

        if st.button(
            "Compare approaches",
            use_container_width=True,
            key="btn_compare_selected_strategies",
        ):
            ok_title, _ = validate_role_title(settings.role_title)
            if not ok_title:
                st.warning("Set a **target role** in the sidebar.")
            else:
                la = str(st.session_state.get("ia_compare_sel_a", _strategy_labels[0]))
                lb = str(st.session_state.get("ia_compare_sel_b", _strategy_labels[1]))
                ka = prompt_strategy_key_from_label(la)
                kb = prompt_strategy_key_from_label(lb)
                if ka == kb:
                    st.warning("Choose two **different** approaches to compare.")
                else:
                    jd = settings.job_description or ""
                    if st.session_state.get("response_language") is None and jd.strip():
                        st.session_state.response_language = detect_language(jd)
                    resolved_lang = st.session_state.get("response_language") or DEFAULT_LANGUAGE
                    nq = int(st.session_state.get("ia_n_questions", 5))
                    err_a = ""
                    err_b = ""
                    with st.spinner("Comparing approaches…"):
                        try:
                            gen_a = generate_questions_from_settings(
                                settings=settings,
                                prompt_strategy=ka,
                                n_questions=nq,
                                session_state=dict(st.session_state),
                                skip_session_rate_limit=False,
                                response_language=resolved_lang,
                                openai_api_key=session_openai_key(),
                            )
                        except Exception as exc:
                            gen_a = None
                            err_a = safe_user_message(exc)
                        else:
                            err_a = ""
                        try:
                            gen_b = generate_questions_from_settings(
                                settings=settings,
                                prompt_strategy=kb,
                                n_questions=nq,
                                session_state=dict(st.session_state),
                                skip_session_rate_limit=True,
                                response_language=resolved_lang,
                                openai_api_key=session_openai_key(),
                            )
                        except Exception as exc:
                            gen_b = None
                            err_b = safe_user_message(exc)
                        else:
                            err_b = ""

                        text_a = ""
                        text_b = ""
                        ok_a = False
                        ok_b = False
                        if gen_a is not None:
                            ok_a = bool(
                                gen_a.ok and gen_a.response and (gen_a.response.text or "").strip()
                            )
                            if gen_a.ok and gen_a.response:
                                text_a = (gen_a.response.text or "").strip()
                            elif not gen_a.ok:
                                err_a = gen_a.error or err_a or "Generation failed."
                        if gen_b is not None:
                            ok_b = bool(
                                gen_b.ok and gen_b.response and (gen_b.response.text or "").strip()
                            )
                            if gen_b.ok and gen_b.response:
                                text_b = (gen_b.response.text or "").strip()
                            elif not gen_b.ok:
                                err_b = gen_b.error or err_b or "Generation failed."

                        trace_a: dict[str, object] | None = None
                        trace_b: dict[str, object] | None = None
                        if (
                            gen_a is not None
                            and gen_a.prompt
                            and gen_a.prompt.debug_trace is not None
                        ):
                            trace_a = gen_a.prompt.debug_trace.as_dict()
                        if (
                            gen_b is not None
                            and gen_b.prompt
                            and gen_b.prompt.debug_trace is not None
                        ):
                            trace_b = gen_b.prompt.debug_trace.as_dict()

                        st.session_state.ia_compare_pair = {
                            "a_key": ka,
                            "b_key": kb,
                            "label_a": la,
                            "label_b": lb,
                            "text_a": text_a,
                            "text_b": text_b,
                            "ok_a": ok_a,
                            "ok_b": ok_b,
                            "err_a": err_a,
                            "err_b": err_b,
                            "trace_a": trace_a,
                            "trace_b": trace_b,
                        }

    pair = st.session_state.get("ia_compare_pair")
    if isinstance(pair, dict) and pair:
        with st.container(border=True):
            render_comparison_results(
                label_a=str(pair["label_a"]),
                label_b=str(pair["label_b"]),
                key_a=str(pair["a_key"]),
                key_b=str(pair["b_key"]),
                text_a=str(pair.get("text_a", "")),
                text_b=str(pair.get("text_b", "")),
                ok_a=bool(pair.get("ok_a")),
                ok_b=bool(pair.get("ok_b")),
                err_a=str(pair.get("err_a", "")),
                err_b=str(pair.get("err_b", "")),
            )
        with st.container(border=True):
            render_evaluation_section(
                settings=settings,
                key_a=str(pair["a_key"]),
                key_b=str(pair["b_key"]),
                label_a=str(pair["label_a"]),
                label_b=str(pair["label_b"]),
            )


def _render_question_generation_tab(settings: UISettings) -> None:
    """Generate and display structured interview questions."""
    render_section_heading(
        "Interview Questions",
        "Create role-specific practice questions from your interview profile.",
    )

    st.number_input(
        "Number of questions",
        min_value=1,
        max_value=20,
        value=int(st.session_state.get("ia_n_questions", 5)),
        step=1,
        help="How many questions to generate in one run.",
        key="ia_n_questions",
    )

    _maybe_run_pending_generation(settings)

    if st.button(
        "Generate interview questions",
        type="primary",
        use_container_width=True,
        key="btn_generate_questions",
    ):
        ok_title, _ = validate_role_title(settings.role_title)
        if not ok_title:
            st.warning("Set a **target role** in the sidebar.")
        else:
            st.session_state.ia_pending_generate = True
            st.rerun()

    with st.expander("Advanced: compare prompting approaches", expanded=False):
        _render_strategy_comparison_block(settings)

    if settings.show_debug:
        nq = int(st.session_state.get("ia_n_questions", 5))
        _pair_dbg = st.session_state.get("ia_compare_pair")
        _extra: dict[str, object] = {
            "n_questions": nq,
            "job_description_len": len(settings.job_description or ""),
        }
        if isinstance(_pair_dbg, dict) and (_pair_dbg.get("trace_a") or _pair_dbg.get("trace_b")):
            _extra["strategy_comparison_traces"] = {
                "a": _pair_dbg.get("trace_a"),
                "b": _pair_dbg.get("trace_b"),
            }
        show_settings_debug(
            settings=settings,
            extra=_extra,
        )
