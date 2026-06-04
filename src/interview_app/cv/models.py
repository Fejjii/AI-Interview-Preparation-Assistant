"""Pydantic models for CV extraction, interview generation, and practice evaluation.

These structures are the contract between ``cv_interview_service``, LLM JSON parsing
(``cv/json_utils``), and the Streamlit display layer. Fields should stay stable
for backward compatibility with saved session payloads where applicable.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CVStructuredExtraction(BaseModel):
    """Structured fields parsed from the CV (LLM pass 1)."""

    profile_summary: str = Field(default="", description="Short professional summary from the CV.")
    skills: list[str] = Field(default_factory=list)
    tools_technologies: list[str] = Field(default_factory=list)
    work_experience: list[str] = Field(
        default_factory=list,
        description="Bullet lines summarizing roles, companies, dates if present.",
    )
    projects: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    detected_roles: list[str] = Field(
        default_factory=list,
        description="Job titles or roles implied by the CV.",
    )


class InterviewQuestionItem(BaseModel):
    """One interview question with suggested answer and follow-ups."""

    question: str
    category: str = Field(
        ...,
        description="e.g. behavioral, technical, leadership, situational",
    )
    difficulty: str
    why_this_question: str = Field(default="", description="Why this fits the candidate's CV.")
    suggested_answer: str = Field(
        default="", description="Concise STAR-style or technical answer outline."
    )
    follow_up_questions: list[str] = Field(default_factory=list)


class CVInterviewGeneration(BaseModel):
    """Interview content derived from structured CV data (LLM pass 2)."""

    candidate_summary: str = Field(
        default="",
        description="2-4 sentence overview grounded in the CV.",
    )
    key_skills: list[str] = Field(default_factory=list)
    detected_roles: list[str] = Field(default_factory=list)
    themes_from_cv: list[str] = Field(
        default_factory=list,
        description="Recurring themes for interview focus.",
    )
    interview_questions: list[InterviewQuestionItem] = Field(default_factory=list)


class CVAnalysisBundle(BaseModel):
    """Full analysis returned to the UI (extraction + generation + metadata)."""

    structured_extraction: CVStructuredExtraction
    generation: CVInterviewGeneration


class PracticeQuestionItem(BaseModel):
    """Single practice prompt — no model answer or follow-ups until evaluation."""

    question: str
    category: str = Field(
        ...,
        description="e.g. behavioral, technical, leadership, situational",
    )
    difficulty: str
    why_this_question: str = Field(default="", description="Why this fits the candidate's CV.")


class CVPracticeQuestionGeneration(BaseModel):
    """Interview questions only (practice mode), grounded in structured CV data."""

    candidate_summary: str = Field(
        default="",
        description="2-4 sentence overview grounded in the CV.",
    )
    key_skills: list[str] = Field(default_factory=list)
    themes_from_cv: list[str] = Field(
        default_factory=list,
        description="Recurring themes for interview focus.",
    )
    interview_questions: list[PracticeQuestionItem] = Field(default_factory=list)


class CVPracticeBundle(BaseModel):
    """Extraction + practice question set (no model answers in generation step)."""

    structured_extraction: CVStructuredExtraction
    practice_generation: CVPracticeQuestionGeneration


class PracticeAnswerEvaluationItem(BaseModel):
    """Structured feedback for one user answer in practice mode."""

    question: str
    user_answer: str
    feedback: str = Field(
        default="", description="Interview-oriented feedback grounded in CV context."
    )
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list, description="What is missing or weak.")
    improved_answer_suggestion: str = Field(
        default="",
        description="Concise improved answer guidance; do not invent CV facts.",
    )
    follow_up_questions: list[str] = Field(default_factory=list)
    score: int | None = Field(
        default=None,
        description="Optional 1-10 score if model provides one.",
    )


class CVPracticeEvaluationBatch(BaseModel):
    """Batch evaluation for all practice answers."""

    evaluations: list[PracticeAnswerEvaluationItem] = Field(default_factory=list)
