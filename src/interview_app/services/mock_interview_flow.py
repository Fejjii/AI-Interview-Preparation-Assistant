"""Mock interview: explicit state machine, turn classification, and topic memory.

Turn classification and interview state are enforced in Python so clarification / meta
turns are never scored; evaluation runs only in ``WAITING_FOR_ANSWER`` when the turn
is classified as a substantive answer.
"""

from __future__ import annotations

import re
from collections.abc import MutableMapping
from enum import Enum
from typing import Any

from interview_app.utils.types import ChatMessage

# Streamlit / in-memory session keys (also used with plain dicts in tests).
KEY_MOCK_PHASE = "ia_mock_phase"
KEY_PENDING_QUESTION = "ia_mock_pending_question"
KEY_INTERVIEW_STATE = "ia_interview_state"
KEY_CANDIDATE_TOPICS = "ia_candidate_topics"
KEY_RECENT_ASKED_QUESTIONS = "ia_recent_asked_questions"


class InterviewState(str, Enum):
    """Explicit interview FSM state persisted in session (mock interview only)."""

    GREETING = "greeting"
    ASKING_QUESTION = "asking_question"
    WAITING_FOR_ANSWER = "waiting_for_answer"
    EVALUATING_ANSWER = "evaluating_answer"
    ASKING_FOLLOW_UP = "asking_follow_up"
    META_CONVERSATION = "meta_conversation"


class UserTurnType(str, Enum):
    """Semantic type of the user's latest message (mock interview routing)."""

    GREETING = "greeting"
    ANSWER = "answer"
    CLARIFICATION = "clarification"
    META = "meta"
    EXPERIENCE = "experience"
    CONTROL = "control"
    CONTEXTUAL_QUESTION_REQUEST = "contextual_question_request"
    OFF_TOPIC = "off_topic"
    OTHER = "other"


class OffTopicCategory(str, Enum):
    """Subtype for off-topic user questions during a pending interview question."""

    STATIC_FACTUAL = "static_factual"
    LIVE_DATA = "live_data"
    UNRELATED = "unrelated"


class MockInterviewTurnKind(str, Enum):
    """Finer-grained mock interview routing (logging, tests, orchestration)."""

    GREETING_OR_START = "greeting_or_start"
    INTERVIEW_ANSWER = "interview_answer"
    CLARIFICATION_QUESTION = "clarification_question"
    META_INSTRUCTION = "meta_instruction"
    PROJECT_EXPERIENCE_STATEMENT = "project_experience_statement"
    REQUEST_CONTEXTUAL_QUESTION = "request_contextual_question"
    GENERIC_QUESTION = "generic_question"
    OFF_TOPIC_QUESTION = "off_topic_question"
    CONTROL_INSTRUCTION = "control_instruction"
    OTHER = "other"


class MockInterviewPhase(str, Enum):
    """Legacy phase labels (kept for session sync and backward compatibility)."""

    NOT_STARTED = "not_started"
    INTERVIEW_STARTED = "interview_started"
    QUESTION_ASKED = "question_asked"
    AWAITING_ANSWER = "awaiting_answer"
    ANSWER_RECEIVED = "answer_received"
    FEEDBACK_GIVEN = "feedback_given"


class UserMessageKind(str, Enum):
    """Legacy classification (maps from ``UserTurnType`` for older call sites)."""

    GREETING = "greeting"
    START_REQUEST = "start_request"
    CONTROL_INSTRUCTION = "control_instruction"
    CLARIFICATION = "clarification"
    CANDIDATE_ANSWER = "candidate_answer"
    RESTART_REQUEST = "restart_request"
    OTHER = "other"


_TECH_LEXICON: frozenset[str] = frozenset(
    {
        "snowflake",
        "bigquery",
        "redshift",
        "databricks",
        "dbt",
        "airflow",
        "prefect",
        "dagster",
        "kafka",
        "pubsub",
        "kinesis",
        "spark",
        "flink",
        "kubernetes",
        "docker",
        "terraform",
        "ansible",
        "redis",
        "memcached",
        "postgres",
        "postgresql",
        "mysql",
        "mongodb",
        "elasticsearch",
        "graphql",
        "rest",
        "grpc",
        "microservices",
        "lambda",
        "ci",
        "cd",
        "github",
        "gitlab",
        "jupyter",
        "mlflow",
        "tensorflow",
        "pytorch",
        "pandas",
        "numpy",
        "etl",
        "elt",
        "cdc",
        "olap",
        "oltp",
        "incremental",
        "scd",
        "slowly",
        "dim",
        "fact",
        "star",
        "schema",
        "normalization",
        "denormalization",
        "partitioning",
        "sharding",
        "replication",
        "backpressure",
        "observability",
        "prometheus",
        "grafana",
        "datadog",
        "opentelemetry",
        "sla",
        "slo",
        "sdlc",
    }
)

_READY_PHRASES: tuple[str, ...] = (
    "let's start",
    "lets start",
    "start interview",
    "start the interview",
    "start a mock interview",
    "begin interview",
    "begin the interview",
    "i'm ready",
    "im ready",
    "i am ready",
    "ready to start",
    "ready for the interview",
    "ready for interview",
    "ready to begin",
    "let's begin",
    "lets begin",
    "next question",
    "ask me a question",
    "ask the first question",
    "another question",
    "different question",
    "new question",
    "continue interview",
    "continue the interview",
    "let us continue",
    "let's continue",
    "lets continue",
    "kick off",
)

_CLARIFICATION_PHRASES: tuple[str, ...] = (
    "what do you mean",
    "can you clarify",
    "could you clarify",
    "clarify if",
    "before i answer",
    "before answering",
    "i don't understand",
    "dont understand",
    "unclear",
    "explain that",
    "say more about",
    "is this interview",
    "is the interview",
    "more theoretical",
    "more practical",
)

_META_PHRASES: tuple[str, ...] = (
    "how long",
    "how much time",
    "what is this",
    "how does this work",
    "what format",
    "are you ai",
    "are you a bot",
    "pause",
    "take a break",
)

_EXPERIENCE_DIGRESSION_MARKERS: tuple[str, ...] = (
    "off topic",
    "unrelated",
    "by the way",
    "random story",
    "not really answering",
    "before we go on",
    "sidebar",
)

_CONTEXT_LINKED_QUESTION_PHRASES: tuple[str, ...] = (
    "related to that",
    "related to this",
    "about that project",
    "about this project",
    "that project",
    "this project",
    "question related",
    "ask me a question related",
    "ask a question related",
    "ask me something about",
    "about what i said",
    "based on what i said",
    "based on my experience",
    "about my experience",
    "dig deeper",
    "drill into",
    "follow up on that",
    "follow-up on that",
    "something technical about",
)

_PENDING_OVERLAP_STOPWORDS: frozenset[str] = frozenset(
    {
        "what",
        "when",
        "where",
        "why",
        "how",
        "would",
        "could",
        "should",
        "does",
        "did",
        "have",
        "has",
        "your",
        "please",
        "tell",
        "describe",
        "explain",
        "about",
        "that",
        "this",
        "with",
        "from",
        "into",
        "some",
        "any",
    }
)

_PROJECT_NARRATIVE_MARKERS: tuple[str, ...] = (
    "i migrated",
    "we migrated",
    "i built",
    "we built",
    "i implemented",
    "we implemented",
    "i designed",
    "we designed",
    "i led",
    "we led",
    "in my last role",
    "in my previous role",
    "at my previous",
    "my team and i",
    "i worked on",
    "we worked on",
    "we moved",
    "i moved",
)


def _user_wants_context_linked_question(t: str) -> bool:
    """User wants the next question tied to their prior story (not a clarification)."""
    return any(p in t for p in _CONTEXT_LINKED_QUESTION_PHRASES)


def clear_mock_interview_runtime_state(session_state: MutableMapping[str, Any] | None) -> None:
    """Reset mock interview keys (no-op if session_state is None)."""
    if session_state is None:
        return
    session_state[KEY_MOCK_PHASE] = MockInterviewPhase.NOT_STARTED.value
    session_state[KEY_PENDING_QUESTION] = None
    session_state[KEY_INTERVIEW_STATE] = InterviewState.GREETING.value
    session_state[KEY_CANDIDATE_TOPICS] = []
    session_state[KEY_RECENT_ASKED_QUESTIONS] = []
    from interview_app.services.context_manager import (
        clear_active_interview_question,
        clear_session_interview_context,
    )

    clear_session_interview_context(session_state)
    clear_active_interview_question(session_state)


def init_mock_interview_runtime_state(session_state: MutableMapping[str, Any]) -> None:
    """Ensure keys exist (idempotent). Migrates legacy phase → interview state once."""
    session_state.setdefault(KEY_MOCK_PHASE, MockInterviewPhase.NOT_STARTED.value)
    if KEY_PENDING_QUESTION not in session_state:
        session_state[KEY_PENDING_QUESTION] = None
    if KEY_INTERVIEW_STATE not in session_state:
        phase = str(session_state.get(KEY_MOCK_PHASE) or "")
        pq = session_state.get(KEY_PENDING_QUESTION)
        if pq and str(pq).strip():
            session_state[KEY_INTERVIEW_STATE] = InterviewState.WAITING_FOR_ANSWER.value
        elif phase == MockInterviewPhase.AWAITING_ANSWER.value:
            session_state[KEY_INTERVIEW_STATE] = InterviewState.WAITING_FOR_ANSWER.value
        else:
            session_state[KEY_INTERVIEW_STATE] = InterviewState.GREETING.value
    session_state.setdefault(KEY_CANDIDATE_TOPICS, [])
    session_state.setdefault(KEY_RECENT_ASKED_QUESTIONS, [])
    from interview_app.services.context_manager import init_session_interview_context

    init_session_interview_context(session_state)


def get_recent_asked_questions(
    session_state: MutableMapping[str, Any] | None,
    *,
    cap: int = 8,
) -> list[str]:
    """Recently asked interview questions (newest last), for skip/next de-duplication."""
    if not session_state:
        return []
    raw = session_state.get(KEY_RECENT_ASKED_QUESTIONS)
    if not isinstance(raw, list):
        return []
    out = [str(x).strip() for x in raw if str(x).strip()]
    return out[-cap:]


def record_asked_question(
    session_state: MutableMapping[str, Any] | None,
    question: str,
    *,
    cap: int = 12,
) -> None:
    """Append a canonical question to recent-asked memory (bounded, de-duplicated)."""
    if session_state is None:
        return
    q = (question or "").strip()
    if not q:
        return
    existing = get_recent_asked_questions(session_state, cap=cap)
    if existing and existing[-1].lower() == q.lower():
        return
    if any(e.lower() == q.lower() for e in existing):
        existing = [e for e in existing if e.lower() != q.lower()]
    existing.append(q)
    session_state[KEY_RECENT_ASKED_QUESTIONS] = existing[-cap:]


def get_interview_state(session_state: MutableMapping[str, Any] | None) -> InterviewState:
    """Resolved FSM state from session (never raises)."""
    if not session_state:
        return InterviewState.GREETING
    pq = session_state.get(KEY_PENDING_QUESTION)
    has_pending = bool(pq and str(pq).strip())
    raw = session_state.get(KEY_INTERVIEW_STATE)
    if raw:
        try:
            st = InterviewState(str(raw))
            if st == InterviewState.GREETING and has_pending:
                return InterviewState.WAITING_FOR_ANSWER
            return st
        except ValueError:
            pass
    if has_pending:
        return InterviewState.WAITING_FOR_ANSWER
    phase = str(session_state.get(KEY_MOCK_PHASE) or "")
    if phase == MockInterviewPhase.AWAITING_ANSWER.value:
        return InterviewState.WAITING_FOR_ANSWER
    return InterviewState.GREETING


def set_interview_state(
    session_state: MutableMapping[str, Any] | None, state: InterviewState
) -> None:
    if session_state is None:
        return
    session_state[KEY_INTERVIEW_STATE] = state.value


def get_pending_question(session_state: MutableMapping[str, Any] | None) -> str | None:
    if not session_state:
        return None
    q = session_state.get(KEY_PENDING_QUESTION)
    if q is None:
        return None
    s = str(q).strip()
    return s or None


def get_candidate_topics(session_state: MutableMapping[str, Any] | None) -> list[str]:
    if not session_state:
        return []
    raw = session_state.get(KEY_CANDIDATE_TOPICS)
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    return []


def append_candidate_topics(
    session_state: MutableMapping[str, Any] | None,
    new_topics: list[str],
    *,
    cap: int = 30,
) -> None:
    """Merge unique topics (case-insensitive), newest last, bounded list."""
    if session_state is None:
        return
    existing = get_candidate_topics(session_state)
    seen = {x.lower() for x in existing}
    for t in new_topics:
        tl = (t or "").strip()
        if len(tl) < 2:
            continue
        key = tl.lower()
        if key not in seen:
            existing.append(tl)
            seen.add(key)
    session_state[KEY_CANDIDATE_TOPICS] = existing[-cap:]


def set_mock_state(
    session_state: MutableMapping[str, Any] | None,
    *,
    pending_question: str | None,
    phase: MockInterviewPhase,
    interview_state: InterviewState | None = None,
) -> None:
    if session_state is None:
        return
    session_state[KEY_PENDING_QUESTION] = pending_question
    session_state[KEY_MOCK_PHASE] = phase.value
    if interview_state is not None:
        session_state[KEY_INTERVIEW_STATE] = interview_state.value
    else:
        if pending_question and str(pending_question).strip():
            session_state[KEY_INTERVIEW_STATE] = InterviewState.WAITING_FOR_ANSWER.value
        elif phase == MockInterviewPhase.FEEDBACK_GIVEN:
            session_state[KEY_INTERVIEW_STATE] = InterviewState.GREETING.value
        elif phase == MockInterviewPhase.NOT_STARTED:
            session_state[KEY_INTERVIEW_STATE] = InterviewState.GREETING.value


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _is_greeting_only(t: str) -> bool:
    if len(t) > 80:
        return False
    greetings = (
        "hi",
        "hey",
        "hello",
        "hi there",
        "hey there",
        "hello there",
        "hola",
        "yo",
        "sup",
        "howdy",
        "good morning",
        "good afternoon",
        "good evening",
    )
    core = t.rstrip("!?.")
    return core in greetings or t in greetings


def _is_restart_request(t: str) -> bool:
    phrases = (
        "new chat",
        "restart",
        "start over",
        "reset interview",
        "reset the interview",
        "clear chat",
        "begin again",
    )
    return any(p in t for p in phrases)


def _is_ready_or_start(t: str) -> bool:
    if "mock interview" in t and len(t) < 120:
        return True
    if any(p in t for p in _READY_PHRASES):
        return True
    if _combined_greeting_ready(t):
        return True
    return False


def _combined_greeting_ready(t: str) -> bool:
    if len(t) > 160:
        return False
    tl = t.lower()
    greeting_hit = any(
        g in tl
        for g in (
            "hello",
            "hi ",
            "hi,",
            "hey",
            "good morning",
            "good afternoon",
        )
    )
    ready_hit = any(w in tl for w in ("ready", "begin", "start", "kick off"))
    return greeting_hit and ready_hit


def _is_clarification(t: str, original: str) -> bool:
    if any(m in t for m in _UNRELATED_REQUEST_MARKERS + _LIVE_DATA_MARKERS):
        return False
    if any(p in t for p in _CLARIFICATION_PHRASES):
        return True
    tl = (original or "").strip().lower()
    if "clarify" in tl or "clarification" in tl:
        return True
    if "?" in original and any(
        s in t
        for s in (
            "can you",
            "could you",
            "would you",
            "is this",
            "are we",
            "should i",
        )
    ):
        if len(t.split()) < 35:
            return True
    return False


def _is_meta(t: str, original: str) -> bool:
    if any(p in t for p in _META_PHRASES):
        return True
    tnorm = _norm(original)
    if (
        any(p in tnorm for p in ("thank you", "thanks", "appreciate it"))
        and len(tnorm.split()) < 12
    ):
        return True
    if tnorm in ("ok", "okay", "k", "sure", "got it", "sounds good", "understood"):
        return True
    question_starts = (
        "tell me about the app",
        "what can you do",
    )
    if any(tnorm.startswith(s) for s in question_starts):
        return True
    return False


_SKIP_NEXT_PHRASES: tuple[str, ...] = (
    "next question",
    "another question",
    "different question",
    "new question",
    "skip this question",
    "skip the question",
    "skip this",
    "skip that",
    "move on",
    "ask something else",
    "ask me another question",
    "give me another question",
    "move to the next question",
    "next question please",
)

_LIVE_DATA_MARKERS: tuple[str, ...] = (
    "today",
    "right now",
    "current price",
    "price today",
    "bitcoin",
    "btc price",
    "stock price",
    "weather today",
    "latest news",
    "live data",
    "market data",
    "exchange rate",
    "crypto price",
    "share price",
)

_UNRELATED_REQUEST_MARKERS: tuple[str, ...] = (
    "recipe",
    "cook pasta",
    "cooking",
    "movie recommendation",
    "song lyrics",
    "play a game",
    "tell me a joke",
)

_STATIC_FACTUAL_MARKERS: tuple[str, ...] = (
    "capital of",
    "population of",
    "who invented",
    "when was",
    "how many continents",
    "what year",
    "tallest mountain",
    "largest country",
)

_KNOWN_STATIC_FACTUAL_ANSWERS: tuple[tuple[str, str], ...] = (
    ("capital of france", "Paris"),
    ("capital of germany", "Berlin"),
    ("capital of italy", "Rome"),
    ("capital of spain", "Madrid"),
    ("capital of uk", "London"),
    ("capital of united kingdom", "London"),
)


def _wants_fresh_question(t: str) -> bool:
    """User asks to move on / replace the current question (not an answer)."""
    if len(t.split()) > 16:
        return False
    core = t.rstrip("!?.")
    if core in ("skip", "next"):
        return True
    return any(p in t for p in _SKIP_NEXT_PHRASES)


def is_skip_or_next_request(message: str) -> bool:
    """True when the user explicitly skips or requests a different next question."""
    t = _norm(message)
    if not t:
        return False
    if infer_focus_override_from_message(message):
        return False
    return _wants_fresh_question(t)


def _is_control_instruction(t: str) -> bool:
    if _wants_fresh_question(t):
        return True
    phrases = (
        "switch to ",
        "change to ",
        "focus on ",
        "let's focus",
        "lets focus",
        "only ask",
        "repeat the question",
        "say the question again",
        "can we switch",
        "could we switch",
    )
    return any(p in t for p in phrases)


def classify_off_topic_category(message: str) -> OffTopicCategory | None:
    """
    Classify a short off-interview user question while a question is pending.

    Returns None when the message is not treated as off-topic.
    """
    t = _norm(message)
    if len(t.split()) > 28:
        return None
    if _wants_fresh_question(t):
        return None
    if any(m in t for m in _LIVE_DATA_MARKERS):
        return OffTopicCategory.LIVE_DATA
    if any(m in t for m in _UNRELATED_REQUEST_MARKERS):
        return OffTopicCategory.UNRELATED
    if _is_clarification(t, message) or _is_meta(t, message):
        return None
    question_like = "?" in (message or "") or t.startswith(
        (
            "what is ",
            "what are ",
            "how much ",
            "who is ",
            "where is ",
            "when is ",
            "can you give ",
            "could you give ",
        )
    )
    if not question_like:
        return None
    if any(m in t for m in _STATIC_FACTUAL_MARKERS):
        return OffTopicCategory.STATIC_FACTUAL
    if t.startswith("what is ") and len(t.split()) <= 10:
        return OffTopicCategory.STATIC_FACTUAL
    return None


def brief_static_factual_answer(message: str) -> str | None:
    """Safe one-line answer for well-known static facts (no live data)."""
    t = _norm(message)
    for needle, answer in _KNOWN_STATIC_FACTUAL_ANSWERS:
        if needle in t:
            return answer
    return None


def _looks_like_off_topic_question(
    t: str,
    original: str,
    pending: str | None,
) -> bool:
    if not pending:
        return False
    if not _looks_like_general_question(original):
        return False
    if _pending_answer_overlap(original, pending):
        return False
    return classify_off_topic_category(original) is not None


def _looks_like_experience_digression(t: str, original: str, pending: str | None) -> bool:
    if not pending:
        return False
    if any(m in t for m in _EXPERIENCE_DIGRESSION_MARKERS):
        return True
    if "in my last role" in t or "in my previous role" in t:
        if (
            "?" not in original
            and len(original.split()) < 25
            and not _looks_like_interview_answer(original)
        ):
            return True
    return False


def _looks_like_interview_answer(text: str) -> bool:
    t = (text or "").strip().lower()
    words = t.split()
    if len(words) >= 20 and "?" not in t:
        return True
    evidence_markers = (
        "i built",
        "i designed",
        "i implemented",
        "in my",
        "for example",
        "we used",
        "we implemented",
        "the trade-off",
        "the approach",
        "i would",
        "i'd approach",
        "because",
        "therefore",
        "we chose",
    )
    if len(words) >= 10 and any(marker in t for marker in evidence_markers):
        return True
    return False


def _looks_like_general_question(text: str) -> bool:
    """Small talk or a meta question, not a substantive interview answer."""
    t = (text or "").strip()
    if len(t) > 400:
        return False
    t_norm = _norm(t)
    question_starts = (
        "tell me ",
        "what is ",
        "what are ",
        "how does ",
        "how do ",
        "why ",
        "explain ",
        "can you ",
        "could you ",
        "when ",
        "where ",
        "who ",
    )
    if t_norm.endswith("?") or any(t_norm.startswith(s) for s in question_starts):
        return True
    if "?" in t and len(t) < 150:
        return True
    social_phrases = (
        "how are you",
        "how's it going",
        "what's up",
    )
    if any(p in t_norm for p in social_phrases):
        return True
    if len(t_norm.split()) <= 5:
        return True
    return False


def _significant_terms(text: str) -> set[str]:
    words = re.findall(r"[a-z][a-z0-9]{3,}", (text or "").lower())
    return {w for w in words if w not in _PENDING_OVERLAP_STOPWORDS}


def _pending_answer_overlap(user_text: str, pending: str | None) -> bool:
    """True when the answer and pending question share substantive terms (topic alignment)."""
    if not pending:
        return False
    pw = _significant_terms(pending)
    uw = _significant_terms(user_text)
    if not pw or not uw:
        return False
    return bool(pw & uw)


def _looks_like_project_experience_narrative(t: str, original: str) -> bool:
    """Volunteered project story cues (not necessarily off-topic if terms overlap the pending question)."""
    if len((original or "").split()) < 8:
        return False
    return any(m in t for m in _PROJECT_NARRATIVE_MARKERS)


def _map_turn_kind_to_user_type(kind: MockInterviewTurnKind) -> UserTurnType:
    if kind == MockInterviewTurnKind.GREETING_OR_START:
        return UserTurnType.GREETING
    if kind == MockInterviewTurnKind.INTERVIEW_ANSWER:
        return UserTurnType.ANSWER
    if kind == MockInterviewTurnKind.CLARIFICATION_QUESTION:
        return UserTurnType.CLARIFICATION
    if kind == MockInterviewTurnKind.META_INSTRUCTION:
        return UserTurnType.META
    if kind == MockInterviewTurnKind.PROJECT_EXPERIENCE_STATEMENT:
        return UserTurnType.EXPERIENCE
    if kind == MockInterviewTurnKind.CONTROL_INSTRUCTION:
        return UserTurnType.CONTROL
    if kind == MockInterviewTurnKind.REQUEST_CONTEXTUAL_QUESTION:
        return UserTurnType.CONTEXTUAL_QUESTION_REQUEST
    if kind == MockInterviewTurnKind.OFF_TOPIC_QUESTION:
        return UserTurnType.OFF_TOPIC
    if kind == MockInterviewTurnKind.GENERIC_QUESTION:
        return UserTurnType.OTHER
    return UserTurnType.OTHER


def detect_mock_interview_turn_kind(
    message: str,
    pending_question: str | None = None,
    session_state: MutableMapping[str, Any] | None = None,
) -> MockInterviewTurnKind:
    """
    Deterministic mock-interview turn classification (orchestration + logging).

    ``session_state`` is reserved for future context-aware signals; routing today is
    message + pending-question driven.
    """
    _ = session_state
    t = _norm(message)
    if not t:
        return MockInterviewTurnKind.OTHER
    if _is_restart_request(t):
        return MockInterviewTurnKind.OTHER
    if _is_control_instruction(t):
        return MockInterviewTurnKind.CONTROL_INSTRUCTION
    if _user_wants_context_linked_question(t):
        return MockInterviewTurnKind.REQUEST_CONTEXTUAL_QUESTION
    if pending_question and _wants_fresh_question(t):
        return MockInterviewTurnKind.CONTROL_INSTRUCTION
    if pending_question and _looks_like_off_topic_question(t, message, pending_question):
        return MockInterviewTurnKind.OFF_TOPIC_QUESTION
    if pending_question and _is_clarification(t, message):
        return MockInterviewTurnKind.CLARIFICATION_QUESTION
    if pending_question and _is_meta(t, message):
        return MockInterviewTurnKind.META_INSTRUCTION
    if not pending_question and _is_ready_or_start(t):
        return MockInterviewTurnKind.GREETING_OR_START
    if not pending_question and _is_greeting_only(t):
        return MockInterviewTurnKind.GREETING_OR_START
    if (
        pending_question
        and _looks_like_project_experience_narrative(t, message)
        and not _pending_answer_overlap(message, pending_question)
    ):
        return MockInterviewTurnKind.PROJECT_EXPERIENCE_STATEMENT
    if pending_question and _looks_like_experience_digression(t, message, pending_question):
        return MockInterviewTurnKind.PROJECT_EXPERIENCE_STATEMENT
    if pending_question:
        if _looks_like_interview_answer(message):
            return MockInterviewTurnKind.INTERVIEW_ANSWER
        if len(t.split()) >= 12 and not _looks_like_general_question(message):
            return MockInterviewTurnKind.INTERVIEW_ANSWER
        if _looks_like_general_question(message):
            if "?" in message and not _is_clarification(t, message):
                off = classify_off_topic_category(message)
                if off is not None:
                    return MockInterviewTurnKind.OFF_TOPIC_QUESTION
            if "?" in message:
                return MockInterviewTurnKind.CLARIFICATION_QUESTION
            return MockInterviewTurnKind.META_INSTRUCTION
        return MockInterviewTurnKind.OTHER
    if _looks_like_job_context(message):
        return MockInterviewTurnKind.OTHER
    return MockInterviewTurnKind.OTHER


def detect_user_turn_type(message: str, *, pending_question: str | None = None) -> UserTurnType:
    """
    Classify the user's message for mock-interview routing.

    When a question is pending, clarification and meta turns must not be treated as answers.
    """
    kind = detect_mock_interview_turn_kind(message, pending_question, None)
    return _map_turn_kind_to_user_type(kind)


def should_evaluate(turn_type: UserTurnType, interview_state: InterviewState) -> bool:
    """
    Evaluation is allowed only while waiting for an answer and the turn is graded as an answer.

    Caller must still ensure a non-empty pending question before running the evaluator.
    """
    if interview_state != InterviewState.WAITING_FOR_ANSWER:
        return False
    return turn_type == UserTurnType.ANSWER


def should_run_full_evaluation(
    *,
    pending_question: str | None,
    turn_type: UserTurnType,
    interview_state: InterviewState,
    user_text: str,
) -> bool:
    """Whether to invoke the answer evaluator (pending Q + FSM + turn type + length guard)."""
    if not (pending_question and pending_question.strip()):
        return False
    if not should_evaluate(turn_type, interview_state):
        return False
    words = _norm(user_text).split()
    if len(words) < 8:
        return False
    return True


def extract_candidate_topics(message: str, max_topics: int = 14) -> list[str]:
    """
    Lightweight topic extraction for contextual follow-ups (technologies, tools, themes).

    Complements the model: deterministic hints improve reliability for names like Snowflake/dbt.
    """
    raw = message or ""
    topics: list[str] = []
    seen: set[str] = set()

    def add(term: str) -> None:
        tl = term.strip()
        if len(tl) < 2:
            return
        k = tl.lower()
        if k in seen:
            return
        seen.add(k)
        topics.append(tl)
        if len(topics) >= max_topics:
            return

    for m in re.finditer(r"\"([^\"]{2,64})\"|'([^']{2,64})'", raw):
        chunk = (m.group(1) or m.group(2) or "").strip()
        if chunk:
            add(chunk)

    for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b", raw):
        chunk = m.group(1).strip()
        if chunk.lower() not in {"i", "we", "the", "a", "an"} and len(chunk) > 2:
            add(chunk)

    lowered = _norm(raw)
    tokens = re.split(r"[^\w+.#-]+", lowered)
    multi = (
        "incremental model",
        "data quality",
        "late arriving",
        "slowly changing",
        "star schema",
        "event driven",
        "machine learning",
        "unit test",
        "integration test",
    )
    for phrase in multi:
        if phrase in lowered:
            add(phrase.title())

    for tok in tokens:
        if tok in _TECH_LEXICON:
            add(tok.upper() if tok in {"etl", "elt", "cdc", "sla", "slo", "ci", "cd"} else tok)

    return topics[:max_topics]


def generate_contextual_follow_up_hints(
    topics: list[str],
    *,
    role: str,
    seniority: str,
    focus: str,
) -> str:
    """Build a short instruction block for the evaluator to anchor the next question."""
    if not topics:
        return ""
    tail = ", ".join(topics[:8])
    return (
        f"Candidate mentioned these concrete topics: {tail}. "
        f"The next follow-up MUST drill into one or more of them (implementation, trade-offs, "
        f"failure modes, validation, or production operations) for a **{seniority}** **{role}** "
        f"candidate; interview focus: **{focus}**."
    )


def build_interviewer_prompt(
    persona: str,
    *,
    interview_round: str,
    focus: str,
    role_title: str,
    seniority: str,
    pending_question: str | None,
    candidate_topics: list[str],
) -> str:
    """System prompt for clarification / meta turns (in-character interviewer, not coach)."""
    from interview_app.prompts.personas import get_persona_interviewer_behavior

    ctx = ""
    if candidate_topics:
        ctx = f"\nTopics the candidate has mentioned so far: {', '.join(candidate_topics[-12:])}."
    pending = (
        f"\nThe current interview question (if they ask about it): {pending_question}"
        if pending_question
        else ""
    )
    return (
        f"{get_persona_interviewer_behavior(persona)}\n\n"
        f"Interview round: {interview_round}. Focus: {focus}. "
        f"Role: {role_title} ({seniority}).{ctx}{pending}\n\n"
        "You are in a live mock interview. The candidate sent a clarification or meta message — "
        "answer naturally in 2–5 short sentences. Do NOT score them. Do NOT ask a new main "
        "question unless they explicitly request the next question. "
        "If they need a concept explained, give a **brief** plain-language explanation (2–3 sentences), "
        "then restate the pending interview question **once** at the end. "
        "Do NOT repeat the same question wording multiple times in one reply. "
        "If they asked about interview format, explain briefly: one question at a time, brief "
        "feedback after answers, then a follow-up."
    )


def _looks_like_job_context(text: str) -> bool:
    t = (text or "").strip().lower()
    if len(t.split()) < 8:
        return False
    cues = (
        "job description",
        "role:",
        "position:",
        "responsibilities",
        "requirements",
        "hiring",
        "company",
    )
    return any(c in t for c in cues)


def _turn_type_to_message_kind(text: str, tt: UserTurnType) -> UserMessageKind:
    """Map new turn types to legacy ``UserMessageKind`` (tests and older helpers)."""
    if tt == UserTurnType.CONTROL:
        return UserMessageKind.CONTROL_INSTRUCTION
    if tt == UserTurnType.CONTEXTUAL_QUESTION_REQUEST:
        return UserMessageKind.CONTROL_INSTRUCTION
    if tt == UserTurnType.CLARIFICATION:
        return UserMessageKind.CLARIFICATION
    if tt == UserTurnType.ANSWER:
        return UserMessageKind.CANDIDATE_ANSWER
    if tt == UserTurnType.GREETING:
        if _is_ready_or_start(_norm(text)):
            return UserMessageKind.START_REQUEST
        return UserMessageKind.GREETING
    return UserMessageKind.OTHER


def user_requests_restart(message: str) -> bool:
    """True when the user asked to reset the mock interview conversation."""
    return bool((message or "").strip()) and _is_restart_request(_norm(message))


def classify_user_message(text: str, *, pending_question: str | None = None) -> UserMessageKind:
    """Legacy classifier; prefer ``detect_user_turn_type`` in new code."""
    if user_requests_restart(text):
        return UserMessageKind.RESTART_REQUEST
    tt = detect_user_turn_type(text, pending_question=pending_question)
    return _turn_type_to_message_kind(text, tt)


def should_run_evaluation(
    *,
    pending_question: str | None,
    kind: UserMessageKind,
    user_text: str,
    interview_state: InterviewState | None = None,
) -> bool:
    """
    Legacy evaluation gate (unit tests). Prefer ``should_run_full_evaluation`` with ``UserTurnType``.
    """
    state = interview_state or InterviewState.WAITING_FOR_ANSWER
    if not (pending_question and pending_question.strip()):
        return False
    if kind in {
        UserMessageKind.GREETING,
        UserMessageKind.START_REQUEST,
        UserMessageKind.CONTROL_INSTRUCTION,
        UserMessageKind.CLARIFICATION,
        UserMessageKind.RESTART_REQUEST,
    }:
        return False
    if state != InterviewState.WAITING_FOR_ANSWER:
        return False
    if kind == UserMessageKind.CANDIDATE_ANSWER:
        return True
    if kind == UserMessageKind.OTHER:
        if _looks_like_general_question(user_text):
            return False
        if len(_norm(user_text).split()) < 8:
            return False
        return True
    return False


def infer_focus_override_from_message(text: str) -> str | None:
    """Map common user phrases to a catalog focus label (approximate sidebar values)."""
    t = _norm(text)
    mapping: tuple[tuple[str, str], ...] = (
        ("behavioral", "Behavioral / Soft Skills"),
        ("soft skill", "Behavioral / Soft Skills"),
        ("technical knowledge", "Technical Knowledge"),
        ("technical", "Technical Knowledge"),
        ("coding", "Coding / Practical Exercise"),
        ("system design", "System Design / Architecture"),
        ("architecture", "System Design / Architecture"),
        ("leadership", "Leadership / Management"),
        ("culture", "Culture Fit / Values"),
        ("cv ", "CV / Experience Deep Dive"),
        ("experience deep", "CV / Experience Deep Dive"),
        ("case study", "Business Case / Strategy"),
        ("strategy", "Business Case / Strategy"),
        ("stakeholder", "Stakeholder Management"),
        ("negotiation", "Salary / Negotiation Preparation"),
    )
    for needle, focus in mapping:
        if needle in t:
            return focus
    return None


def extract_follow_up_from_feedback_message(assistant_text: str) -> str | None:
    """Parse the next question line from mock-interview feedback formatting."""
    text = (assistant_text or "").strip()
    if not text:
        return None
    has_score = (
        "**Overall score" in text
        or "**Overall Score" in text
        or "**Score:" in text
        or re.search(r"(?m)^##\s*Overall\s+[Ss]core\s*$", text)
        or re.search(r"(?m)^##\s*score\s*$", text, re.IGNORECASE)
    )
    if not has_score and "Score:" not in text:
        return None

    patterns = (
        r"\*\*Next Follow-up Question:\*\*\s*\n+\s*(.+?)(?:\n\n|\Z)",
        r"\*\*Follow-up:\*\*\s*\n+\s*(.+?)(?:\n\n|\Z)",
        r"(?mi)^##\s*Next Follow-up Question\s*\n+\s*(.+?)(?:\n\n|\Z)",
        r"(?mi)^##\s*Follow-up\s*\n+(.*?)(?=\n##\s|\Z)",
    )
    for pat in patterns:
        m = re.search(pat, text, re.DOTALL | re.IGNORECASE)
        if m:
            line = m.group(1).strip()
            first = line.splitlines()[0].strip() if line else ""
            if first:
                return first
    return None


def sync_mock_interview_session_from_messages(
    session_state: MutableMapping[str, Any] | None,
    messages: list[ChatMessage],
) -> None:
    """Rebuild pending question + phase from transcript (e.g. after loading a session)."""
    if session_state is None:
        return
    if not messages:
        clear_mock_interview_runtime_state(session_state)
        return

    last_assistant: str | None = None
    for m in reversed(messages):
        if m.role == "assistant":
            last_assistant = m.content
            break
    if not last_assistant:
        clear_mock_interview_runtime_state(session_state)
        return

    fu = extract_follow_up_from_feedback_message(last_assistant)
    if fu:
        set_mock_state(
            session_state,
            pending_question=fu,
            phase=MockInterviewPhase.AWAITING_ANSWER,
            interview_state=InterviewState.WAITING_FOR_ANSWER,
        )
    elif (
        "**Overall score" in last_assistant
        or "**Overall Score" in last_assistant
        or "**Score:" in last_assistant
        or re.search(r"(?m)^##\s*Overall\s+[Ss]core\s*$", last_assistant)
    ):
        set_mock_state(
            session_state,
            pending_question=None,
            phase=MockInterviewPhase.FEEDBACK_GIVEN,
            interview_state=InterviewState.GREETING,
        )
    else:
        pending = last_assistant.strip()
        set_mock_state(
            session_state,
            pending_question=pending,
            phase=MockInterviewPhase.AWAITING_ANSWER,
            interview_state=InterviewState.WAITING_FOR_ANSWER,
        )

    from interview_app.services.context_manager import (
        rebuild_session_interview_context_from_transcript,
    )

    rebuild_session_interview_context_from_transcript(session_state, messages)
