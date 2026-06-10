"""CV Interview Prep workspace tab."""

import json
from typing import Any

import streamlit as st

from interview_app.app import cv_session_state as cvs
from interview_app.app.tabs.shared import render_section_heading, session_openai_key
from interview_app.app.ui_settings import UISettings
from interview_app.cv.models import (
    CVAnalysisBundle,
    CVPracticeBundle,
    CVPracticeEvaluationBatch,
    CVStructuredExtraction,
)
from interview_app.services.cv_interview_service import (
    CVInterviewServiceResult,
    run_cv_interview_pipeline,
    run_cv_practice_evaluation,
    to_export_dict,
    to_practice_export_dict,
)
from interview_app.ui.display import (
    show_cv_analysis_bundle,
    show_cv_practice_bundle,
    show_cv_practice_evaluation_batch,
    show_guardrail_summary,
    show_prompt_debug,
    show_settings_debug,
)
from interview_app.ui.presentation import show_technical_metadata
from interview_app.utils.errors import safe_user_message
from interview_app.utils.usage_formatting import format_usage_summary


def _render_cv_interview_tab(settings: UISettings) -> None:
    """Upload CV, run extraction + interview generation with guardrails (practice vs full prep)."""
    render_section_heading(
        "CV Interview Prep",
        "Upload your resume, set a target role, and generate tailored interview preparation.",
    )

    uploader_key = f"cv_file_uploader_v{cvs.get_cv_workspace_version(st.session_state)}"
    uploaded = st.file_uploader(
        "Upload CV",
        type=["pdf", "docx"],
        help="PDF or Word (.docx). Max size enforced server-side.",
        key=uploader_key,
    )
    has_uploaded_file = uploaded is not None

    target_role = st.text_input(
        "Target role",
        value=settings.role_title or "",
        help="Questions are tailored to this title and your CV.",
        key="cv_target_role_input",
    )

    interview_type = st.selectbox(
        "Interview type",
        options=["HR / behavioral", "technical", "mixed"],
        index=2,
        key="cv_interview_type",
    )

    difficulty = st.selectbox(
        "Difficulty",
        options=["easy", "medium", "hard"],
        index=1,
        key="cv_difficulty",
    )

    n_questions = int(
        st.number_input(
            "Number of questions",
            min_value=1,
            max_value=20,
            value=int(st.session_state.get("cv_n_questions", 5)),
            key="cv_n_questions",
        )
    )

    with st.expander("Optional: company & job context", expanded=False):
        target_company = st.text_input(
            "Target company (optional)",
            value="",
            key="cv_target_company",
        )
        extra_job = st.text_area(
            "Job description or extra context (optional)",
            value="",
            height=90,
            key="cv_extra_job_context",
        )

    analysis_ready = cvs.analysis_ready(st.session_state)
    cv_ver = cvs.get_cv_workspace_version(st.session_state)

    st.markdown("**Generate preparation**")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.caption("Practice questions to answer yourself.")
        btn_practice = st.button(
            "Generate practice questions",
            type="primary",
            use_container_width=True,
            key="cv_btn_practice",
            disabled=not has_uploaded_file,
        )
    with col_b:
        st.caption("Full prep with model answers.")
        btn_full = st.button(
            "Generate full prep",
            use_container_width=True,
            key="cv_btn_full_prep",
            disabled=not has_uploaded_file,
        )
    with col_c:
        reset_cv = st.button(
            "Reset",
            use_container_width=True,
            key="cv_btn_reset",
            help="Clear CV results and start over.",
        )

    if not has_uploaded_file:
        st.info("Upload a PDF or DOCX to get started.")

    if reset_cv:
        cvs.clear_cv_workspace(st.session_state)
        st.rerun()

    def _apply_cv_result(
        result: CVInterviewServiceResult,
        *,
        step: str,
        file_meta: dict[str, Any] | None = None,
    ) -> None:
        show_guardrail_summary(guardrails=result.guardrails)
        if not result.ok:
            st.session_state[cvs.KEY_LAST_ERROR] = result.error or "Unknown error."
            if step == "analyze":
                cvs.on_full_analyze_failure(st.session_state)
            elif result.generation_mode == "practice_questions":
                cvs.on_practice_regenerate_failure(st.session_state)
            else:
                cvs.on_regenerate_failure(st.session_state)
            return

        if result.practice_bundle is not None:
            if result.bundle is not None:
                st.session_state[cvs.KEY_LAST_ERROR] = (
                    "Internal error: both practice and full prep bundles set."
                )
                cvs.on_full_analyze_failure(st.session_state)
                return
            st.session_state.pop(cvs.KEY_LAST_ERROR, None)
            st.session_state[cvs.KEY_STRUCTURED] = (
                result.practice_bundle.structured_extraction.model_dump()
            )
            st.session_state[cvs.KEY_PRACTICE_BUNDLE] = result.practice_bundle.model_dump()
            st.session_state[cvs.KEY_ACTIVE_MODE] = "practice"
            st.session_state.pop(cvs.KEY_BUNDLE, None)
            st.session_state.pop(cvs.KEY_EXPORT, None)
            st.session_state.pop(cvs.KEY_PRACTICE_EVAL_BATCH, None)
            st.session_state.pop(cvs.KEY_PRACTICE_EVAL_ERROR, None)
            st.session_state[cvs.KEY_DEBUG_RAW_LEN] = len(result.raw_extracted_text or "")
            st.session_state[cvs.KEY_DEBUG_CLEAN] = (result.cleaned_text_for_llm or "")[:2000]
            if result.file_hash:
                st.session_state[cvs.KEY_FILE_HASH] = result.file_hash
            if step == "analyze" and file_meta:
                st.session_state[cvs.KEY_FILE_META] = file_meta
            if step == "analyze":
                cvs.on_full_analyze_success(st.session_state)
            else:
                cvs.on_regenerate_success(st.session_state)
            if result.regenerate_only:
                st.toast("Practice questions regenerated (same CV analysis).")
            else:
                st.toast("CV analyzed — practice questions ready.")
        elif result.bundle is not None:
            st.session_state.pop(cvs.KEY_LAST_ERROR, None)
            st.session_state[cvs.KEY_STRUCTURED] = result.bundle.structured_extraction.model_dump()
            st.session_state[cvs.KEY_BUNDLE] = result.bundle.model_dump()
            st.session_state[cvs.KEY_EXPORT] = to_export_dict(result.bundle)
            st.session_state[cvs.KEY_ACTIVE_MODE] = "full_prep"
            st.session_state.pop(cvs.KEY_PRACTICE_BUNDLE, None)
            st.session_state.pop(cvs.KEY_PRACTICE_EVAL_BATCH, None)
            st.session_state.pop(cvs.KEY_PRACTICE_EVAL_ERROR, None)
            st.session_state[cvs.KEY_DEBUG_RAW_LEN] = len(result.raw_extracted_text or "")
            st.session_state[cvs.KEY_DEBUG_CLEAN] = (result.cleaned_text_for_llm or "")[:2000]
            if result.file_hash:
                st.session_state[cvs.KEY_FILE_HASH] = result.file_hash
            if step == "analyze" and file_meta:
                st.session_state[cvs.KEY_FILE_META] = file_meta
            if step == "analyze":
                cvs.on_full_analyze_success(st.session_state)
            else:
                cvs.on_regenerate_success(st.session_state)
            if result.regenerate_only:
                st.toast("Full prep regenerated (same CV analysis).")
            else:
                st.toast("CV analyzed — full prep ready.")
        else:
            st.session_state[cvs.KEY_LAST_ERROR] = "No generation output returned."
            if step == "analyze":
                cvs.on_full_analyze_failure(st.session_state)
            elif result.generation_mode == "practice_questions":
                cvs.on_practice_regenerate_failure(st.session_state)
            else:
                cvs.on_regenerate_failure(st.session_state)
            return

        usage_lines = [s for r in result.llm_responses if (s := format_usage_summary(r))]
        if usage_lines and show_technical_metadata():
            with st.expander("LLM usage", expanded=False):
                for i, line in enumerate(usage_lines, start=1):
                    st.caption(f"Call {i}: {line}")

        if settings.show_debug:
            meta = [
                {
                    "model": r.model,
                    "provider": r.provider,
                    "latency_ms": r.latency_ms,
                    "usage": r.usage.model_dump() if r.usage else None,
                    "raw_response_id": r.raw_response_id,
                    "phase": "regenerate_only" if result.regenerate_only else "full",
                    "generation_mode": result.generation_mode,
                }
                for r in result.llm_responses
            ]
            with st.expander("LLM calls (debug)", expanded=False):
                st.code(json.dumps(meta, indent=2), language="json")
            if result.extraction_system_prompt and result.extraction_user_prompt:
                with st.expander("Prompts: CV extraction (debug)", expanded=False):
                    show_prompt_debug(
                        system_prompt=result.extraction_system_prompt,
                        user_prompt=result.extraction_user_prompt,
                    )
            if result.generation_system_prompt and result.generation_user_prompt:
                with st.expander("Prompts: interview generation (debug)", expanded=False):
                    show_prompt_debug(
                        system_prompt=result.generation_system_prompt,
                        user_prompt=result.generation_user_prompt,
                    )
            with st.expander("Extracted text preview (debug)", expanded=False):
                st.caption("First ~2000 chars after cleaning / guardrails (not the raw file).")
                st.code(
                    st.session_state.get(cvs.KEY_DEBUG_CLEAN) or "",
                    language="text",
                )
            fm = st.session_state.get(cvs.KEY_FILE_META) or {}
            show_settings_debug(
                settings=settings,
                extra={
                    "cv_file_hash": result.file_hash,
                    "cv_raw_extracted_chars": st.session_state.get(cvs.KEY_DEBUG_RAW_LEN),
                    "cv_file_meta": fm,
                    "cv_analysis_ready": cvs.analysis_ready(st.session_state),
                    "cv_active_mode": st.session_state.get(cvs.KEY_ACTIVE_MODE),
                },
            )

    if btn_practice:
        st.session_state.pop(cvs.KEY_LAST_ERROR, None)
        if not uploaded:
            st.warning("Please upload a PDF or DOCX file.")
        else:
            try:
                file_bytes = uploaded.getvalue()
                with st.spinner("Analyzing CV and generating practice questions…"):
                    result = run_cv_interview_pipeline(
                        filename=uploaded.name,
                        file_bytes=file_bytes,
                        target_role=target_role,
                        interview_type=interview_type,
                        difficulty=difficulty,
                        n_questions=n_questions,
                        model=settings.model_preset,
                        temperature=settings.temperature,
                        max_tokens=settings.max_tokens,
                        top_p=settings.top_p,
                        session_state=dict(st.session_state),
                        regenerate_questions_only=False,
                        target_company=target_company,
                        extra_job_context=extra_job,
                        generation_mode="practice_questions",
                        openai_api_key=session_openai_key(),
                    )
            except Exception as exc:
                st.session_state[cvs.KEY_LAST_ERROR] = safe_user_message(exc)
                cvs.on_full_analyze_failure(st.session_state)
            else:
                _apply_cv_result(
                    result,
                    step="analyze",
                    file_meta={
                        "filename": uploaded.name,
                        "size_bytes": len(file_bytes),
                    },
                )

    elif btn_full:
        st.session_state.pop(cvs.KEY_LAST_ERROR, None)
        if not uploaded:
            st.warning("Please upload a PDF or DOCX file.")
        else:
            try:
                file_bytes = uploaded.getvalue()
                with st.spinner(
                    "Analyzing CV and generating full prep (overview + answers + follow-ups)…"
                ):
                    result = run_cv_interview_pipeline(
                        filename=uploaded.name,
                        file_bytes=file_bytes,
                        target_role=target_role,
                        interview_type=interview_type,
                        difficulty=difficulty,
                        n_questions=n_questions,
                        model=settings.model_preset,
                        temperature=settings.temperature,
                        max_tokens=settings.max_tokens,
                        top_p=settings.top_p,
                        session_state=dict(st.session_state),
                        regenerate_questions_only=False,
                        target_company=target_company,
                        extra_job_context=extra_job,
                        generation_mode="full_prep",
                        openai_api_key=session_openai_key(),
                    )
            except Exception as exc:
                st.session_state[cvs.KEY_LAST_ERROR] = safe_user_message(exc)
                cvs.on_full_analyze_failure(st.session_state)
            else:
                _apply_cv_result(
                    result,
                    step="analyze",
                    file_meta={
                        "filename": uploaded.name,
                        "size_bytes": len(file_bytes),
                    },
                )

    with st.expander("Regenerate from last CV", expanded=False):
        st.caption("Uses your last successful analysis — no need to re-upload.")
        regen_col1, regen_col2 = st.columns(2)
        with regen_col1:
            regen_practice = st.button(
                "Regenerate practice questions",
                use_container_width=True,
                key="cv_btn_regen_practice",
                disabled=not analysis_ready,
            )
        with regen_col2:
            regen_full = st.button(
                "Regenerate full prep",
                use_container_width=True,
                key="cv_btn_regen_full",
                disabled=not analysis_ready,
            )

    if regen_practice:
        st.session_state.pop(cvs.KEY_LAST_ERROR, None)
        raw = st.session_state.get(cvs.KEY_STRUCTURED)
        if not raw:
            st.warning("Run **Analyze CV** successfully first.")
        else:
            try:
                cached_extraction = CVStructuredExtraction.model_validate(raw)
                with st.spinner("Regenerating practice questions…"):
                    result = run_cv_interview_pipeline(
                        filename=None,
                        file_bytes=None,
                        target_role=target_role,
                        interview_type=interview_type,
                        difficulty=difficulty,
                        n_questions=n_questions,
                        model=settings.model_preset,
                        temperature=settings.temperature,
                        max_tokens=settings.max_tokens,
                        top_p=settings.top_p,
                        session_state=dict(st.session_state),
                        regenerate_questions_only=True,
                        cached_extraction=cached_extraction,
                        cached_file_hash=str(st.session_state.get(cvs.KEY_FILE_HASH) or ""),
                        target_company=target_company,
                        extra_job_context=extra_job,
                        generation_mode="practice_questions",
                        openai_api_key=session_openai_key(),
                    )
            except Exception as exc:
                st.session_state[cvs.KEY_LAST_ERROR] = safe_user_message(exc)
                cvs.on_practice_regenerate_failure(st.session_state)
            else:
                _apply_cv_result(result, step="regenerate")

    elif regen_full:
        st.session_state.pop(cvs.KEY_LAST_ERROR, None)
        raw = st.session_state.get(cvs.KEY_STRUCTURED)
        if not raw:
            st.warning("Run **Analyze CV** successfully first.")
        else:
            try:
                cached_extraction = CVStructuredExtraction.model_validate(raw)
                with st.spinner("Regenerating full prep…"):
                    result = run_cv_interview_pipeline(
                        filename=None,
                        file_bytes=None,
                        target_role=target_role,
                        interview_type=interview_type,
                        difficulty=difficulty,
                        n_questions=n_questions,
                        model=settings.model_preset,
                        temperature=settings.temperature,
                        max_tokens=settings.max_tokens,
                        top_p=settings.top_p,
                        session_state=dict(st.session_state),
                        regenerate_questions_only=True,
                        cached_extraction=cached_extraction,
                        cached_file_hash=str(st.session_state.get(cvs.KEY_FILE_HASH) or ""),
                        target_company=target_company,
                        extra_job_context=extra_job,
                        generation_mode="full_prep",
                        openai_api_key=session_openai_key(),
                    )
            except Exception as exc:
                st.session_state[cvs.KEY_LAST_ERROR] = safe_user_message(exc)
                cvs.on_regenerate_failure(st.session_state)
            else:
                _apply_cv_result(result, step="regenerate")

    err_banner = st.session_state.get(cvs.KEY_LAST_ERROR)
    if err_banner:
        st.error(f"**CV step failed**\n\n{err_banner}")

    active_mode = str(st.session_state.get(cvs.KEY_ACTIVE_MODE) or "none")
    practice_raw = st.session_state.get(cvs.KEY_PRACTICE_BUNDLE)
    bundle_raw = st.session_state.get(cvs.KEY_BUNDLE)
    show_practice = active_mode == "practice" and bool(practice_raw)
    show_full = active_mode == "full_prep" and bool(bundle_raw)

    if show_practice:
        try:
            pb = CVPracticeBundle.model_validate(practice_raw)
            show_cv_practice_bundle(bundle=pb)
            st.markdown("### Your practice questions")
            st.caption("Answer each prompt, then run evaluation when ready.")
            any_answer = False
            for i, item in enumerate(pb.practice_generation.interview_questions):
                st.markdown(f"**{i + 1}. ({item.category} · {item.difficulty})** {item.question}")
                if item.why_this_question:
                    st.caption(f"Why this question: {item.why_this_question}")
                ans = st.text_area(
                    "Your answer",
                    height=120,
                    key=f"cv_pa_{cv_ver}_{i}",
                    label_visibility="collapsed",
                    placeholder="Type your answer here…",
                )
                if (ans or "").strip():
                    any_answer = True

            st.session_state[cvs.KEY_PRACTICE_ANSWERS] = {
                str(i): (st.session_state.get(f"cv_pa_{cv_ver}_{i}") or "")
                for i in range(len(pb.practice_generation.interview_questions))
            }

            eval_err = st.session_state.get(cvs.KEY_PRACTICE_EVAL_ERROR)
            if eval_err:
                st.error(f"**Evaluation failed**\n\n{eval_err}")

            if st.button(
                "Evaluate my answers",
                type="primary",
                use_container_width=True,
                key="cv_btn_evaluate_practice",
                disabled=not any_answer,
            ):
                raw_struct = st.session_state.get(cvs.KEY_STRUCTURED)
                if not raw_struct or not practice_raw:
                    st.warning(
                        "Practice session is incomplete. Run **Analyze CV & generate questions** again."
                    )
                else:
                    qa_pairs: list[tuple[str, str]] = []
                    for i, q in enumerate(pb.practice_generation.interview_questions):
                        a = (st.session_state.get(f"cv_pa_{cv_ver}_{i}") or "").strip()
                        if a:
                            qa_pairs.append((q.question, a))
                    try:
                        extraction = CVStructuredExtraction.model_validate(raw_struct)
                        with st.spinner("Evaluating your answers…"):
                            eval_result = run_cv_practice_evaluation(
                                structured_extraction=extraction,
                                qa_pairs=qa_pairs,
                                target_role=target_role,
                                interview_type=interview_type,
                                difficulty=difficulty,
                                model=settings.model_preset,
                                temperature=settings.temperature,
                                max_tokens=settings.max_tokens,
                                top_p=settings.top_p,
                                session_state=dict(st.session_state),
                                openai_api_key=session_openai_key(),
                            )
                    except Exception as exc:
                        st.session_state[cvs.KEY_PRACTICE_EVAL_ERROR] = safe_user_message(exc)
                    else:
                        show_guardrail_summary(guardrails=eval_result.guardrails)
                        if not eval_result.ok or eval_result.batch is None:
                            st.session_state[cvs.KEY_PRACTICE_EVAL_ERROR] = (
                                eval_result.error or "Evaluation failed."
                            )
                        else:
                            st.session_state.pop(cvs.KEY_PRACTICE_EVAL_ERROR, None)
                            st.session_state[cvs.KEY_PRACTICE_EVAL_BATCH] = (
                                eval_result.batch.model_dump()
                            )
                            st.toast("Evaluation complete.")
                            if (
                                settings.show_debug
                                and eval_result.system_prompt
                                and eval_result.user_prompt
                            ):
                                show_prompt_debug(
                                    system_prompt=eval_result.system_prompt,
                                    user_prompt=eval_result.user_prompt,
                                )
                        st.rerun()

            eval_raw = st.session_state.get(cvs.KEY_PRACTICE_EVAL_BATCH)
            if eval_raw:
                try:
                    eval_batch = CVPracticeEvaluationBatch.model_validate(eval_raw)
                    show_cv_practice_evaluation_batch(batch=eval_batch)
                except Exception:
                    pass

            with st.expander("More actions", expanded=False):
                export_p = to_practice_export_dict(pb)
                st.download_button(
                    label="Export practice questions (JSON)",
                    data=json.dumps(export_p, indent=2, ensure_ascii=False),
                    file_name="cv_practice_questions.json",
                    mime="application/json",
                    key="cv_download_practice_export",
                    use_container_width=True,
                )
        except Exception:
            pass

    if show_full:
        try:
            bundle = CVAnalysisBundle.model_validate(bundle_raw)
            show_cv_analysis_bundle(bundle=bundle)
            export_payload = st.session_state.get(cvs.KEY_EXPORT)
            if isinstance(export_payload, dict):
                with st.expander("More actions", expanded=False):
                    st.download_button(
                        label="Export questions & answers (JSON)",
                        data=json.dumps(export_payload, indent=2, ensure_ascii=False),
                        file_name="cv_interview_prep.json",
                        mime="application/json",
                        key="cv_download_export_area",
                        use_container_width=True,
                    )
        except Exception:
            pass

    if (
        settings.show_debug
        and not btn_practice
        and not btn_full
        and not regen_practice
        and not regen_full
    ):
        show_settings_debug(
            settings=settings,
            extra={
                "cv_analysis_ready": cvs.analysis_ready(st.session_state),
                "cv_workspace_version": cvs.get_cv_workspace_version(st.session_state),
                "cv_active_mode": active_mode,
            },
        )
