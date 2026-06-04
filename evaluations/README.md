# Deterministic evaluations

Lightweight, fixture-driven checks that the Interview Preparation Assistant returns the **right kind of output** for each user task—without calling OpenAI.

## What these evaluations cover

| Suite | Protects against |
| --- | --- |
| Question relevance | Off-topic or irrelevant generated questions for a given role, seniority, round, and JD snippet |
| Answer evaluation shape | Regressions in markdown feedback parsing (score, strengths, gaps, model answer, follow-ups) |
| CV extraction shape | Invalid or incomplete structured CV JSON; delimiter-breakout in uploaded CV text |
| Guardrails | Prompt-injection bypasses vs legitimate interview prep (including multilingual/obfuscated cases) |
| Mock interview routing | Clarifications scored as answers; control commands (`next`, `repeat`, `start`) mis-routed |

Implementation lives in:

- `evaluations/checks.py` — small, transparent keyword/shape helpers
- `evaluations/fixtures/*.json` — human-readable case data
- `tests/evaluations/` — pytest tests that load fixtures and call production parsers/classifiers

## What they do not cover

- Live LLM answer quality, creativity, or factual correctness
- Streamlit UI rendering or session persistence
- Rate limiting, moderation API behavior, or network failures
- End-to-end flows that require an API key

Optional **live LLM quality evaluation** (sampling, rubric scoring, cost tracking) can be added later as a separate, explicitly opt-in suite.

## How this differs from unit tests

| | Unit tests (`tests/unit`, `tests/test_*`) | Evaluations (`tests/evaluations`) |
| --- | --- | --- |
| Goal | Correctness of functions, edge cases, mocks | Task-level behavior: “right answer type for right user task” |
| Data | Often inline in test files | Shared JSON fixtures for portfolio-friendly review |
| LLM | Never in unit tests | Never here either (mocked outputs only) |
| Audience | Developers refactoring code | You + reviewers validating product behavior |

Both run under pytest; evaluations are grouped so you can run them separately.

## Commands

From the repository root (with your virtualenv active):

```bash
# Full test suite (includes evaluations)
pytest

# Evaluations only
pytest tests/evaluations -v

# Convenience runner (same as above)
python evaluations/run_evaluations.py

# Lint / format (includes evaluations/)
ruff check src tests evaluations
black --check src tests evaluations
```

## Adding a new case

1. Edit the relevant file under `evaluations/fixtures/`.
2. Give the case a unique `"id"` string.
3. Run `pytest tests/evaluations -v` and fix any failures.
4. If you need new check logic, extend `evaluations/checks.py` minimally—prefer reusing production parsers.

### Fixture files

- `fixtures/question_relevance_cases.json` — `mocked_questions`, `expected_focus_keywords`, `disallowed_irrelevant_themes`; set `"expect_pass": false` for negative cases
- `fixtures/answer_evaluation_cases.json` — `mock_llm_output`, `expect_valid`, optional `expect_follow_up`, `min_score`
- `fixtures/cv_extraction_cases.json` — `mock_llm_json`, optional `cv_text_snippet` + `strip_delimiters`
- `fixtures/guardrail_cases.json` — `text`, `expect_allow`, optional `strict`
- `fixtures/mock_interview_routing_cases.json` — `message`, `pending_question`, `expected_turn_kind`

## Design principles

- **Deterministic** — same input, same verdict every run
- **Cheap** — no API keys, no network
- **Transparent** — keyword and shape checks, not hidden LLM judges
- **Honest failures** — assertions surface fixture `id` via pytest parametrize
