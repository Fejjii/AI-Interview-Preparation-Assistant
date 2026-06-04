"""Extract structured interview topics from candidate messages (mock interview).

Pure functions: tools, technologies, concepts, projects, and achievements used to
drive context-aware follow-up questions. Complements LLM generation with stable,
testable signals.
"""

from __future__ import annotations

import re
from typing import Any, TypedDict


class InterviewTopicsDict(TypedDict):
    """Structured buckets for session context (lists are JSON-serializable for Streamlit)."""

    tools: list[str]
    technologies: list[str]
    concepts: list[str]
    projects: list[str]
    achievements: list[str]
    domains: list[str]
    recent_topics: list[str]
    last_project_summary: str


_TITLE_CASE_STOPWORDS: frozenset[str] = frozenset(
    {
        "I",
        "We",
        "The",
        "A",
        "An",
        "My",
        "Our",
        "Your",
        "They",
        "He",
        "She",
        "It",
        "This",
        "That",
        "These",
        "Those",
        "Before",
        "After",
        "When",
        "While",
        "Since",
        "Because",
        "However",
        "Also",
        "Then",
        "Here",
        "There",
        "During",
        "For",
        "From",
        "With",
        "Without",
        "Not",
        "But",
        "And",
        "Or",
    }
)


def empty_interview_topics() -> InterviewTopicsDict:
    return {
        "tools": [],
        "technologies": [],
        "concepts": [],
        "projects": [],
        "achievements": [],
        "domains": [],
        "recent_topics": [],
        "last_project_summary": "",
    }


_TOOLS: frozenset[str] = frozenset(
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
        "kinesis",
        "pubsub",
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
        "looker",
        "tableau",
        "power bi",
        "powerbi",
        "fivetran",
        "matillion",
        "segment",
        "snowplow",
        "github actions",
        "gitlab ci",
        "jenkins",
        "circleci",
        "datadog",
        "prometheus",
        "grafana",
        "splunk",
        "mlflow",
        "kubeflow",
        "vertex ai",
        "sagemaker",
    }
)

_TECHNOLOGIES: frozenset[str] = frozenset(
    {
        "etl",
        "elt",
        "cdc",
        "olap",
        "oltp",
        "api",
        "apis",
        "rest",
        "grpc",
        "graphql",
        "microservices",
        "streaming",
        "batch",
        "real-time",
        "real time",
        "machine learning",
        "ml",
        "deep learning",
        "nlp",
        "ci/cd",
        "ci cd",
        "devops",
        "iac",
        "serverless",
        "lambda",
        "kubernetes",
        "containerization",
        "orchestration",
        "data warehouse",
        "data lake",
        "lakehouse",
        "nosql",
        "sql",
        "python",
        "scala",
        "java",
        "typescript",
        "javascript",
        "golang",
        "rustlang",
        "rust",
        "go",
    }
)

_CONCEPT_PHRASES: tuple[tuple[str, str], ...] = (
    ("incremental model", "Incremental models"),
    ("incremental models", "Incremental models"),
    ("slowly changing dimension", "Slowly changing dimensions"),
    ("scd type", "SCD modeling"),
    ("data modeling", "Data modeling"),
    ("dimensional model", "Dimensional modeling"),
    ("star schema", "Star schema"),
    ("snowflake schema", "Snowflake schema"),
    ("normalization", "Normalization"),
    ("denormalization", "Denormalization"),
    ("partitioning", "Partitioning"),
    ("clustering", "Clustering (data layout)"),
    ("data quality", "Data quality"),
    ("data governance", "Data governance"),
    ("lineage", "Data lineage"),
    ("schema evolution", "Schema evolution"),
    ("late arriving", "Late-arriving data"),
    ("idempotency", "Idempotency"),
    ("exactly once", "Exactly-once semantics"),
    ("at least once", "At-least-once delivery"),
    ("backfill", "Backfill"),
    ("orchestration", "Pipeline orchestration"),
    ("monitoring", "Monitoring / observability"),
    ("sla", "SLA / SLO"),
    ("disaster recovery", "Disaster recovery"),
    ("high availability", "High availability"),
    ("horizontal scaling", "Horizontal scaling"),
    ("vertical scaling", "Vertical scaling"),
    ("caching", "Caching strategy"),
    ("indexing", "Indexing / query optimization"),
    ("cost optimization", "Cost optimization"),
    ("unit test", "Unit testing"),
    ("integration test", "Integration testing"),
    ("contract test", "Contract testing"),
)

_PROJECT_PHRASES: tuple[tuple[str, str], ...] = (
    ("migration", "Data / system migration"),
    ("migrated", "Migration project"),
    ("modernization", "Modernization"),
    ("legacy", "Legacy replacement"),
    ("data warehouse", "Data warehouse initiative"),
    ("greenfield", "Greenfield build"),
    ("dashboard", "Analytics / dashboard delivery"),
    ("ml pipeline", "ML pipeline"),
    ("feature store", "Feature store"),
    ("self-service", "Self-service analytics"),
    ("real-time pipeline", "Real-time pipeline"),
    ("batch pipeline", "Batch pipeline"),
    ("event-driven", "Event-driven architecture"),
)

_DOMAIN_PHRASES: tuple[tuple[str, str], ...] = (
    ("data warehouse", "Data warehousing"),
    ("data lake", "Data lake / lakehouse"),
    ("analytics", "Analytics engineering"),
    ("machine learning", "Machine learning"),
    ("ml ", "Machine learning"),
    ("streaming", "Streaming data"),
    ("batch", "Batch data processing"),
    ("data engineering", "Data engineering"),
    ("platform", "Data platform"),
    ("migration", "Data / system migration"),
)

_ACHIEVEMENT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"reduced\s+(?:runtime|latency|cost|spend)\s+by\s+[\d.]+\s*%", re.I),
        "Reduced runtime/cost (quantified)",
    ),
    (
        re.compile(r"(?:cut|lowered|decreased|improved)\s+.+\s+by\s+[\d.]+\s*%", re.I),
        "Quantified improvement",
    ),
    (
        re.compile(r"\b(?:p\d{2}|p99|p95|latency)\b.+(?:ms|second|sec)", re.I),
        "Latency / SLO improvement",
    ),
    (re.compile(r"scaled\s+(?:to|from)\s+", re.I), "Scaled system traffic/data"),
    (
        re.compile(r"(?:handled|processed)\s+[\d.]+\s*(?:tb|gb|pb|million|billion)\s", re.I),
        "Scale / volume handled",
    ),
    (re.compile(r"(?:saved|cut)\s+\$[\d,]+", re.I), "Cost savings ($)"),
)


def _norm_lower(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _dedupe_preserve(items: list[str], cap: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        k = x.strip().lower()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(x.strip())
        if len(out) >= cap:
            break
    return out


def extract_interview_topics(message: str, *, max_per_bucket: int = 20) -> InterviewTopicsDict:
    """
    Pull tools, technologies, concepts, projects, and achievements from one user message.

    Returns a fresh dict per call; merging into session state is handled by ``context_manager``.
    """
    raw = message or ""
    lowered = _norm_lower(raw)
    out = empty_interview_topics()

    # Quoted proper nouns / project names
    for m in re.finditer(r"\"([^\"]{2,72})\"|'([^']{2,72})'", raw):
        label = (m.group(1) or m.group(2) or "").strip()
        if label and len(label) > 2:
            out["projects"].append(label)

    # Title-case sequences (e.g. product names)
    for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,4})\b", raw):
        label = m.group(1).strip()
        first_word = label.split()[0]
        if first_word in _TITLE_CASE_STOPWORDS or label in _TITLE_CASE_STOPWORDS:
            continue
        if len(label) > 3:
            out["tools"].append(label)

    tokens = re.split(r"[^\w+/.\-]+", lowered)
    for tok in tokens:
        if not tok:
            continue
        tl = tok.lower().rstrip(".,)")
        if tl in _TOOLS:
            display = (
                tl.upper()
                if tl in {"etl", "elt", "cdc", "sla", "ml", "api", "sql", "oltp", "olap"}
                else tl
            )
            out["tools"].append(display if tl != "power bi" else "Power BI")
        if tl in _TECHNOLOGIES or (tl in {"ml", "ai"}):
            out["technologies"].append(tl.upper() if len(tl) <= 4 and tl.isalpha() else tl)

    for needle, label in _CONCEPT_PHRASES:
        if needle in lowered:
            out["concepts"].append(label)

    for needle, label in _PROJECT_PHRASES:
        if needle in lowered:
            out["projects"].append(label)

    for rx, label in _ACHIEVEMENT_PATTERNS:
        if rx.search(raw):
            out["achievements"].append(label)

    # Achievement: plain "by 40%" near reduce/improve
    if re.search(
        r"(?:reduced|reduce|improved|improve|cut|decreased|decrease|increased|increase|optimized).{0,40}\d+\s*%",
        lowered,
    ):
        if not out["achievements"]:
            out["achievements"].append("Quantified performance/cost outcome")

    for needle, label in _DOMAIN_PHRASES:
        if needle in lowered:
            out["domains"].append(label)

    for key in ("tools", "technologies", "concepts", "projects", "achievements", "domains"):
        out[key] = _dedupe_preserve(out[key], max_per_bucket)  # type: ignore[literal-required]

    flat = flatten_interview_topics(out, max_items=12)
    out["recent_topics"] = flat
    if interview_topics_non_empty(out):
        summary = re.sub(r"\s+", " ", raw.strip())
        out["last_project_summary"] = summary[:280] + ("…" if len(summary) > 280 else "")

    return out


def interview_topics_non_empty(d: InterviewTopicsDict | dict[str, Any]) -> bool:
    """True if any bucket has at least one entry."""
    for k in ("tools", "technologies", "concepts", "projects", "achievements", "domains"):
        if d.get(k):
            return True
    return False


def flatten_interview_topics(
    d: InterviewTopicsDict | dict[str, Any], *, max_items: int = 40
) -> list[str]:
    """Single list for evaluator hints and legacy ``candidate_topics`` merging."""
    items: list[str] = []
    order = ("tools", "technologies", "concepts", "projects", "achievements", "domains")
    for k in order:
        for x in d.get(k, []) or []:
            s = str(x).strip()
            if s:
                items.append(s)
    return _dedupe_preserve(items, max_items)
