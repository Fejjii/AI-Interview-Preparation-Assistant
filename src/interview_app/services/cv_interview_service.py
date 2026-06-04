"""CV-based interview preparation: extract text, structure profile JSON, generate questions.

Orchestrates file parsing (``cv/document_parser``), guardrails, LLM calls for
extraction and generation, and optional practice-mode evaluation. Used by the
**CV Interview Prep** workspace in ``app/layout``.

Primary outputs: ``CVInterviewServiceResult`` and related dataclasses in
``cv/models``; errors surface as user-safe strings plus guardrail maps for UI.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any, Literal

from interview_app.app.interview_form_config import validate_role_title
from interview_app.config.settings import get_security_settings
from interview_app.cv.document_parser import extract_text_from_cv_bytes
from interview_app.cv.exceptions import CVExtractionError, CVFileValidationError
from interview_app.cv.json_utils import parse_llm_json_model
from interview_app.cv.models import (
    CVAnalysisBundle,
    CVInterviewGeneration,
    CVPracticeBundle,
    CVPracticeEvaluationBatch,
    CVPracticeQuestionGeneration,
    CVStructuredExtraction,
)
from interview_app.cv.prompt_builders import (
    system_prompt_cv_extraction,
    system_prompt_cv_interview_generation,
    system_prompt_cv_practice_evaluate_answers,
    system_prompt_cv_practice_questions_only,
    user_prompt_cv_extraction,
    user_prompt_cv_interview_generation,
    user_prompt_cv_practice_evaluate_answers,
    user_prompt_cv_practice_questions_only,
)
from interview_app.cv.text_cleaning import normalize_cv_text
from interview_app.llm.model_settings import resolve_openai_model_id
from interview_app.llm.openai_client import LLMClient
from interview_app.security.guards import GuardrailResult
from interview_app.security.pipeline import run_input_pipeline, run_output_pipeline
from interview_app.security.rate_limiter import check_rate_limit
from interview_app.utils.errors import safe_user_message
from interview_app.utils.types import LLMResponse

logger = logging.getLogger("interview_app.cv")

_SERVICE_NAME = "cv_interview"

CVGenerationMode = Literal["full_prep", "practice_questions"]


def file_content_hash(data: bytes) -> str:
    """SHA-256 hex digest for caching and debug (not security-sensitive)."""
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class CVInterviewServiceResult:
    """Result of CV analysis / question generation."""

    ok: bool
    bundle: CVAnalysisBundle | None
    practice_bundle: CVPracticeBundle | None
    error: str | None
    guardrails: dict[str, GuardrailResult]
    raw_extracted_text: str
    cleaned_text_for_llm: str
    file_hash: str | None
    extraction_system_prompt: str | None
    extraction_user_prompt: str | None
    generation_system_prompt: str | None
    generation_user_prompt: str | None
    llm_responses: list[LLMResponse]
    regenerate_only: bool = False
    generation_mode: CVGenerationMode = "full_prep"


@dataclass(frozen=True)
class CVPracticeEvaluationServiceResult:
    """Result of practice-mode batch evaluation."""

    ok: bool
    batch: CVPracticeEvaluationBatch | None
    error: str | None
    guardrails: dict[str, GuardrailResult]
    system_prompt: str | None
    user_prompt: str | None
    llm_responses: list[LLMResponse]


def run_cv_interview_pipeline(
    *,
    filename: str | None,
    file_bytes: bytes | None,
    target_role: str,
    interview_type: str,
    difficulty: str,
    n_questions: int,
    model: str,
    temperature: float,
    max_tokens: int,
    top_p: float | None,
    session_state: dict[str, Any] | None,
    regenerate_questions_only: bool = False,
    cached_extraction: CVStructuredExtraction | None = None,
    cached_file_hash: str | None = None,
    target_company: str = "",
    extra_job_context: str = "",
    generation_mode: CVGenerationMode = "full_prep",
    openai_api_key: str | None = None,
) -> CVInterviewServiceResult:
    """
    Full pipeline: optional file extraction → guardrails → structured CV JSON → interview JSON.

    When ``regenerate_questions_only`` is True, ``cached_extraction`` must be provided and
    file upload fields are ignored.

    ``generation_mode``:
    - ``full_prep``: model answers + follow-ups (default).
    - ``practice_questions``: questions only; no model answers in this step.
    """
    guards: dict[str, GuardrailResult] = {}
    llm_responses: list[LLMResponse] = []
    raw_text = ""
    cleaned = ""
    file_hash: str | None = cached_file_hash
    ext_sys: str | None = None
    ext_user: str | None = None
    gen_sys: str | None = None
    gen_user: str | None = None

    sec = get_security_settings()

    ok_title, role_trimmed = validate_role_title(target_role)
    if not ok_title:
        return CVInterviewServiceResult(
            ok=False,
            bundle=None,
            practice_bundle=None,
            error="Please enter a target role title.",
            guardrails=guards,
            raw_extracted_text="",
            cleaned_text_for_llm="",
            file_hash=file_hash,
            extraction_system_prompt=None,
            extraction_user_prompt=None,
            generation_system_prompt=None,
            generation_user_prompt=None,
            llm_responses=[],
            generation_mode=generation_mode,
        )

    role_pipe = run_input_pipeline(
        role_trimmed,
        field_name="cv_target_role",
        max_chars=200,
        session_state=None,
        check_rate=False,
        service=_SERVICE_NAME,
    )
    if role_pipe.guardrail:
        guards["cv_target_role"] = role_pipe.guardrail
    if not role_pipe.ok:
        return CVInterviewServiceResult(
            ok=False,
            bundle=None,
            practice_bundle=None,
            error=role_pipe.error or "Invalid target role.",
            guardrails=guards,
            raw_extracted_text="",
            cleaned_text_for_llm="",
            file_hash=file_hash,
            extraction_system_prompt=None,
            extraction_user_prompt=None,
            generation_system_prompt=None,
            generation_user_prompt=None,
            llm_responses=[],
            generation_mode=generation_mode,
        )

    # Optional UI fields: do NOT run the guardrail pipeline on empty strings — validate_user_input
    # rejects empty input, which produced misleading "cv_extra_job_context" failures in debug.
    company_cleaned = ""
    company_stripped = (target_company or "").strip()
    if company_stripped:
        company_pipe = run_input_pipeline(
            company_stripped,
            field_name="cv_target_company",
            max_chars=200,
            session_state=None,
            check_rate=False,
            service=_SERVICE_NAME,
        )
        if company_pipe.guardrail:
            guards["cv_target_company"] = company_pipe.guardrail
        if not company_pipe.ok:
            return CVInterviewServiceResult(
                ok=False,
                bundle=None,
                practice_bundle=None,
                error=company_pipe.error or "Target company text rejected by guardrails.",
                guardrails=guards,
                raw_extracted_text="",
                cleaned_text_for_llm="",
                file_hash=file_hash,
                extraction_system_prompt=None,
                extraction_user_prompt=None,
                generation_system_prompt=None,
                generation_user_prompt=None,
                llm_responses=[],
                generation_mode=generation_mode,
            )
        company_cleaned = company_pipe.cleaned_text

    jd_cleaned = ""
    jd_stripped = (extra_job_context or "").strip()
    if jd_stripped:
        jd_pipe = run_input_pipeline(
            jd_stripped,
            field_name="cv_extra_job_context",
            max_chars=4000,
            session_state=None,
            check_rate=False,
            service=_SERVICE_NAME,
        )
        if jd_pipe.guardrail:
            guards["cv_extra_job_context"] = jd_pipe.guardrail
        if not jd_pipe.ok:
            return CVInterviewServiceResult(
                ok=False,
                bundle=None,
                practice_bundle=None,
                error=jd_pipe.error or "Extra job context rejected by guardrails.",
                guardrails=guards,
                raw_extracted_text="",
                cleaned_text_for_llm="",
                file_hash=file_hash,
                extraction_system_prompt=None,
                extraction_user_prompt=None,
                generation_system_prompt=None,
                generation_user_prompt=None,
                llm_responses=[],
                generation_mode=generation_mode,
            )
        jd_cleaned = jd_pipe.cleaned_text

    nq = max(1, min(20, int(n_questions)))

    extraction: CVStructuredExtraction | None = (
        cached_extraction if regenerate_questions_only else None
    )

    if not regenerate_questions_only:
        if not filename or file_bytes is None:
            return CVInterviewServiceResult(
                ok=False,
                bundle=None,
                practice_bundle=None,
                error="Please upload a CV file.",
                guardrails=guards,
                raw_extracted_text="",
                cleaned_text_for_llm="",
                file_hash=file_hash,
                extraction_system_prompt=None,
                extraction_user_prompt=None,
                generation_system_prompt=None,
                generation_user_prompt=None,
                llm_responses=[],
            )
        file_hash = file_content_hash(file_bytes)
        logger.info(
            "CV upload: filename=%s bytes=%d hash_prefix=%s",
            filename,
            len(file_bytes),
            file_hash[:12],
        )
        try:
            raw_text = extract_text_from_cv_bytes(
                filename=filename,
                data=file_bytes,
                max_bytes=sec.cv_max_file_bytes,
            )
        except (CVFileValidationError, CVExtractionError) as exc:
            logger.warning("CV extract failed: %s", exc)
            return CVInterviewServiceResult(
                ok=False,
                bundle=None,
                practice_bundle=None,
                error=str(exc),
                guardrails=guards,
                raw_extracted_text="",
                cleaned_text_for_llm="",
                file_hash=file_hash,
                extraction_system_prompt=None,
                extraction_user_prompt=None,
                generation_system_prompt=None,
                generation_user_prompt=None,
                llm_responses=[],
                generation_mode=generation_mode,
            )

        logger.info("CV raw text length before normalize: %s", len(raw_text or ""))
        cleaned = normalize_cv_text(raw_text)
        logger.info("CV text length after normalize: %s", len(cleaned or ""))
        if not cleaned.strip():
            empty_msg = (
                "Could not extract readable text from this file. "
                "For PDFs, common causes are: scanned/image-only pages, empty file, or copy protection. "
                "Try a text-based PDF, export from Word as DOCX, or use OCR first."
            )
            logger.warning(
                "CV analysis blocked: empty text after normalize (raw_len=%s file=%s)",
                len(raw_text or ""),
                filename,
            )
            return CVInterviewServiceResult(
                ok=False,
                bundle=None,
                practice_bundle=None,
                error=empty_msg,
                guardrails=guards,
                raw_extracted_text=raw_text,
                cleaned_text_for_llm="",
                file_hash=file_hash,
                extraction_system_prompt=None,
                extraction_user_prompt=None,
                generation_system_prompt=None,
                generation_user_prompt=None,
                llm_responses=[],
            )

        cv_pipe = run_input_pipeline(
            cleaned,
            field_name="cv_text",
            max_chars=sec.cv_max_text_chars,
            session_state=session_state,
            check_rate=True,
            service=_SERVICE_NAME,
        )
        logger.info(
            "CV guardrail cv_text: ok=%s cleaned_len=%s",
            cv_pipe.ok,
            len(cv_pipe.cleaned_text or ""),
        )
        if cv_pipe.guardrail:
            guards["cv_text"] = cv_pipe.guardrail
        if not cv_pipe.ok:
            return CVInterviewServiceResult(
                ok=False,
                bundle=None,
                practice_bundle=None,
                error=cv_pipe.error or "CV text rejected by guardrails.",
                guardrails=guards,
                raw_extracted_text=raw_text,
                cleaned_text_for_llm=cv_pipe.cleaned_text,
                file_hash=file_hash,
                extraction_system_prompt=None,
                extraction_user_prompt=None,
                generation_system_prompt=None,
                generation_user_prompt=None,
                llm_responses=[],
                generation_mode=generation_mode,
            )

        cleaned = cv_pipe.cleaned_text
        ext_sys = system_prompt_cv_extraction()
        ext_user = user_prompt_cv_extraction(cleaned)

        try:
            client = LLMClient(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                api_key=openai_api_key,
            )
            logger.info("CV extraction LLM call starting model=%s", model)
            resp1 = client.generate_response(
                system_prompt=ext_sys,
                user_prompt=ext_user,
                top_p=top_p,
                temperature=temperature,
                max_tokens=max_tokens,
                llm_route="cv_extraction",
            )
        except Exception as exc:
            return CVInterviewServiceResult(
                ok=False,
                bundle=None,
                practice_bundle=None,
                error=safe_user_message(exc),
                guardrails=guards,
                raw_extracted_text=raw_text,
                cleaned_text_for_llm=cleaned,
                file_hash=file_hash,
                extraction_system_prompt=ext_sys,
                extraction_user_prompt=ext_user,
                generation_system_prompt=None,
                generation_user_prompt=None,
                llm_responses=[],
                generation_mode=generation_mode,
            )

        llm_responses.append(resp1)
        out1 = run_output_pipeline(resp1.text, expect_json=True, service=_SERVICE_NAME)
        if not out1.safe:
            return CVInterviewServiceResult(
                ok=False,
                bundle=None,
                practice_bundle=None,
                error=out1.reason or "Extraction output rejected.",
                guardrails=guards,
                raw_extracted_text=raw_text,
                cleaned_text_for_llm=cleaned,
                file_hash=file_hash,
                extraction_system_prompt=ext_sys,
                extraction_user_prompt=ext_user,
                generation_system_prompt=None,
                generation_user_prompt=None,
                llm_responses=llm_responses,
                generation_mode=generation_mode,
            )

        try:
            extraction = parse_llm_json_model(out1.text, CVStructuredExtraction)
        except ValueError as exc:
            logger.warning("CV extraction JSON parse failed: %s", exc)
            return CVInterviewServiceResult(
                ok=False,
                bundle=None,
                practice_bundle=None,
                error="Could not parse structured CV data from the model. Please try again.",
                guardrails=guards,
                raw_extracted_text=raw_text,
                cleaned_text_for_llm=cleaned,
                file_hash=file_hash,
                extraction_system_prompt=ext_sys,
                extraction_user_prompt=ext_user,
                generation_system_prompt=None,
                generation_user_prompt=None,
                llm_responses=llm_responses,
                generation_mode=generation_mode,
            )
    else:
        if extraction is None:
            return CVInterviewServiceResult(
                ok=False,
                bundle=None,
                practice_bundle=None,
                error="No cached CV analysis found. Upload and analyze a CV first.",
                guardrails=guards,
                raw_extracted_text="",
                cleaned_text_for_llm="",
                file_hash=file_hash,
                extraction_system_prompt=None,
                extraction_user_prompt=None,
                generation_system_prompt=None,
                generation_user_prompt=None,
                llm_responses=[],
                generation_mode=generation_mode,
            )
        cleaned = "(cached extraction; raw CV text not reloaded in this session step)"

    assert extraction is not None

    if regenerate_questions_only and session_state is not None:
        rl = check_rate_limit(session_state, service=_SERVICE_NAME)
        if not rl.allowed:
            return CVInterviewServiceResult(
                ok=False,
                bundle=None,
                practice_bundle=None,
                error=rl.message or "Rate limit exceeded. Please wait and try again.",
                guardrails=guards,
                raw_extracted_text=raw_text,
                cleaned_text_for_llm=cleaned,
                file_hash=file_hash,
                extraction_system_prompt=ext_sys,
                extraction_user_prompt=ext_user,
                generation_system_prompt=None,
                generation_user_prompt=None,
                llm_responses=llm_responses,
                generation_mode=generation_mode,
            )

    structured_json = json.dumps(extraction.model_dump(), ensure_ascii=False)
    if generation_mode == "practice_questions":
        gen_sys = system_prompt_cv_practice_questions_only()
        gen_user = user_prompt_cv_practice_questions_only(
            structured_cv_json=structured_json,
            target_role=role_pipe.cleaned_text,
            interview_type=interview_type,
            difficulty=difficulty,
            n_questions=nq,
            target_company=company_cleaned,
            extra_job_context=jd_cleaned,
        )
    else:
        gen_sys = system_prompt_cv_interview_generation()
        gen_user = user_prompt_cv_interview_generation(
            structured_cv_json=structured_json,
            target_role=role_pipe.cleaned_text,
            interview_type=interview_type,
            difficulty=difficulty,
            n_questions=nq,
            target_company=company_cleaned,
            extra_job_context=jd_cleaned,
        )

    try:
        client = LLMClient(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            api_key=openai_api_key,
        )
        logger.info(
            "CV interview generation LLM call starting model=%s mode=%s",
            model,
            generation_mode,
        )
        resp2 = client.generate_response(
            system_prompt=gen_sys,
            user_prompt=gen_user,
            top_p=top_p,
            temperature=temperature,
            max_tokens=max_tokens,
            model=resolve_openai_model_id(model),
            llm_route="cv_interview_generation",
        )
    except Exception as exc:
        return CVInterviewServiceResult(
            ok=False,
            bundle=None,
            practice_bundle=None,
            error=safe_user_message(exc),
            guardrails=guards,
            raw_extracted_text=raw_text,
            cleaned_text_for_llm=cleaned,
            file_hash=file_hash,
            extraction_system_prompt=ext_sys,
            extraction_user_prompt=ext_user,
            generation_system_prompt=gen_sys,
            generation_user_prompt=gen_user,
            llm_responses=llm_responses,
            generation_mode=generation_mode,
        )

    llm_responses.append(resp2)
    out2 = run_output_pipeline(resp2.text, expect_json=True, service=_SERVICE_NAME)
    if not out2.safe:
        return CVInterviewServiceResult(
            ok=False,
            bundle=None,
            practice_bundle=None,
            error=out2.reason or "Interview generation output rejected.",
            guardrails=guards,
            raw_extracted_text=raw_text,
            cleaned_text_for_llm=cleaned,
            file_hash=file_hash,
            extraction_system_prompt=ext_sys,
            extraction_user_prompt=ext_user,
            generation_system_prompt=gen_sys,
            generation_user_prompt=gen_user,
            llm_responses=llm_responses,
            generation_mode=generation_mode,
        )

    if generation_mode == "practice_questions":
        try:
            practice_generation = parse_llm_json_model(out2.text, CVPracticeQuestionGeneration)
        except ValueError as exc:
            logger.warning("CV practice questions JSON parse failed: %s", exc)
            return CVInterviewServiceResult(
                ok=False,
                bundle=None,
                practice_bundle=None,
                error="Could not parse practice questions from the model. Please try again.",
                guardrails=guards,
                raw_extracted_text=raw_text,
                cleaned_text_for_llm=cleaned,
                file_hash=file_hash,
                extraction_system_prompt=ext_sys,
                extraction_user_prompt=ext_user,
                generation_system_prompt=gen_sys,
                generation_user_prompt=gen_user,
                llm_responses=llm_responses,
                generation_mode=generation_mode,
            )

        practice_bundle = CVPracticeBundle(
            structured_extraction=extraction,
            practice_generation=practice_generation,
        )
        return CVInterviewServiceResult(
            ok=True,
            bundle=None,
            practice_bundle=practice_bundle,
            error=None,
            guardrails=guards,
            raw_extracted_text=raw_text,
            cleaned_text_for_llm=cleaned if not regenerate_questions_only else cleaned,
            file_hash=file_hash,
            extraction_system_prompt=ext_sys,
            extraction_user_prompt=ext_user,
            generation_system_prompt=gen_sys,
            generation_user_prompt=gen_user,
            llm_responses=llm_responses,
            regenerate_only=regenerate_questions_only,
            generation_mode="practice_questions",
        )

    try:
        generation = parse_llm_json_model(out2.text, CVInterviewGeneration)
    except ValueError as exc:
        logger.warning("CV generation JSON parse failed: %s", exc)
        return CVInterviewServiceResult(
            ok=False,
            bundle=None,
            practice_bundle=None,
            error="Could not parse interview content from the model. Please try again.",
            guardrails=guards,
            raw_extracted_text=raw_text,
            cleaned_text_for_llm=cleaned,
            file_hash=file_hash,
            extraction_system_prompt=ext_sys,
            extraction_user_prompt=ext_user,
            generation_system_prompt=gen_sys,
            generation_user_prompt=gen_user,
            llm_responses=llm_responses,
            generation_mode=generation_mode,
        )

    bundle = CVAnalysisBundle(structured_extraction=extraction, generation=generation)
    return CVInterviewServiceResult(
        ok=True,
        bundle=bundle,
        practice_bundle=None,
        error=None,
        guardrails=guards,
        raw_extracted_text=raw_text,
        cleaned_text_for_llm=cleaned if not regenerate_questions_only else cleaned,
        file_hash=file_hash,
        extraction_system_prompt=ext_sys,
        extraction_user_prompt=ext_user,
        generation_system_prompt=gen_sys,
        generation_user_prompt=gen_user,
        llm_responses=llm_responses,
        regenerate_only=regenerate_questions_only,
        generation_mode="full_prep",
    )


def to_export_dict(bundle: CVAnalysisBundle) -> dict[str, Any]:
    """Serialize bundle for JSON download (stable keys)."""
    return {
        "structured_extraction": bundle.structured_extraction.model_dump(),
        "generation": bundle.generation.model_dump(),
    }


def to_practice_export_dict(bundle: CVPracticeBundle) -> dict[str, Any]:
    """Serialize practice bundle for JSON download."""
    return {
        "structured_extraction": bundle.structured_extraction.model_dump(),
        "practice_generation": bundle.practice_generation.model_dump(),
    }


def run_cv_practice_evaluation(
    *,
    structured_extraction: CVStructuredExtraction,
    qa_pairs: list[tuple[str, str]],
    target_role: str,
    interview_type: str,
    difficulty: str,
    model: str,
    temperature: float,
    max_tokens: int,
    top_p: float | None,
    session_state: dict[str, Any] | None,
    openai_api_key: str | None = None,
) -> CVPracticeEvaluationServiceResult:
    """
    Evaluate user-written practice answers against structured CV and questions.

    ``qa_pairs`` is (question_text, user_answer) for each item to score; empty answers should be omitted by caller.
    """
    guards: dict[str, GuardrailResult] = {}
    llm_responses: list[LLMResponse] = []
    sec = get_security_settings()

    ok_title, role_trimmed = validate_role_title(target_role)
    if not ok_title:
        return CVPracticeEvaluationServiceResult(
            ok=False,
            batch=None,
            error="Please enter a target role title.",
            guardrails=guards,
            system_prompt=None,
            user_prompt=None,
            llm_responses=[],
        )

    role_pipe = run_input_pipeline(
        role_trimmed,
        field_name="cv_target_role",
        max_chars=200,
        session_state=None,
        check_rate=False,
        service=_SERVICE_NAME,
    )
    if role_pipe.guardrail:
        guards["cv_target_role"] = role_pipe.guardrail
    if not role_pipe.ok:
        return CVPracticeEvaluationServiceResult(
            ok=False,
            batch=None,
            error=role_pipe.error or "Invalid target role.",
            guardrails=guards,
            system_prompt=None,
            user_prompt=None,
            llm_responses=[],
        )

    if not qa_pairs:
        return CVPracticeEvaluationServiceResult(
            ok=False,
            batch=None,
            error="No answers to evaluate.",
            guardrails=guards,
            system_prompt=None,
            user_prompt=None,
            llm_responses=[],
        )

    payload = [{"question": q, "user_answer": a} for q, a in qa_pairs]
    qa_json = json.dumps(payload, ensure_ascii=False)

    qa_pipe = run_input_pipeline(
        qa_json,
        field_name="cv_practice_answers",
        max_chars=min(sec.cv_max_text_chars, 24_000),
        session_state=session_state,
        check_rate=True,
        service=_SERVICE_NAME,
    )
    if qa_pipe.guardrail:
        guards["cv_practice_answers"] = qa_pipe.guardrail
    if not qa_pipe.ok:
        return CVPracticeEvaluationServiceResult(
            ok=False,
            batch=None,
            error=qa_pipe.error or "Practice answers rejected by guardrails.",
            guardrails=guards,
            system_prompt=None,
            user_prompt=None,
            llm_responses=[],
        )

    structured_json = json.dumps(structured_extraction.model_dump(), ensure_ascii=False)
    sys_p = system_prompt_cv_practice_evaluate_answers()
    usr_p = user_prompt_cv_practice_evaluate_answers(
        structured_cv_json=structured_json,
        target_role=role_pipe.cleaned_text,
        interview_type=interview_type,
        difficulty=difficulty,
        qa_json=qa_pipe.cleaned_text,
    )

    try:
        client = LLMClient(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            api_key=openai_api_key,
        )
        logger.info("CV practice evaluation LLM call starting model=%s", model)
        resp = client.generate_response(
            system_prompt=sys_p,
            user_prompt=usr_p,
            top_p=top_p,
            temperature=temperature,
            max_tokens=max_tokens,
            model=resolve_openai_model_id(model),
            llm_route="cv_practice_evaluation",
        )
    except Exception as exc:
        return CVPracticeEvaluationServiceResult(
            ok=False,
            batch=None,
            error=safe_user_message(exc),
            guardrails=guards,
            system_prompt=sys_p,
            user_prompt=usr_p,
            llm_responses=[],
        )

    llm_responses.append(resp)
    out = run_output_pipeline(resp.text, expect_json=True, service=_SERVICE_NAME)
    if not out.safe:
        return CVPracticeEvaluationServiceResult(
            ok=False,
            batch=None,
            error=out.reason or "Evaluation output rejected.",
            guardrails=guards,
            system_prompt=sys_p,
            user_prompt=usr_p,
            llm_responses=llm_responses,
        )

    try:
        batch = parse_llm_json_model(out.text, CVPracticeEvaluationBatch)
    except ValueError as exc:
        logger.warning("CV practice evaluation JSON parse failed: %s", exc)
        return CVPracticeEvaluationServiceResult(
            ok=False,
            batch=None,
            error="Could not parse evaluation results from the model. Please try again.",
            guardrails=guards,
            system_prompt=sys_p,
            user_prompt=usr_p,
            llm_responses=llm_responses,
        )

    return CVPracticeEvaluationServiceResult(
        ok=True,
        batch=batch,
        error=None,
        guardrails=guards,
        system_prompt=sys_p,
        user_prompt=usr_p,
        llm_responses=llm_responses,
    )
