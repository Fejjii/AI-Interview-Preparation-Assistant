# AI Interview Preparation Assistant

**Streamlit + OpenAI** interview coach for technical and behavioral practice: mock interviews, tailored question generation, answer feedback, and CV-based prep—with guardrails, prompt strategies, and deterministic evaluations suitable for portfolio and demo deployment.

**Live demo:** coming soon

**Screenshots:** coming after deployment (see [docs/screenshots/](docs/screenshots/))

---

## Features

| Area | What it does |
|------|----------------|
| **Mock interview** | Chat-style practice with turn routing (clarifications vs answers), scoring, follow-up questions, and optional **voice answer** input (transcribe → review → send) |
| **Interview questions** | Role-aware question sets; optional **Compare Prompt Strategies** side by side |
| **CV interview prep** | PDF/DOCX upload, structured extraction, practice or full prep modes |
| **Answer feedback** | Markdown-parsed scores, strengths, gaps, model answers, follow-ups |
| **Sidebar setup** | Role, seniority, round, focus, persona, difficulty, model preset, prompt strategy, language |
| **Demo / BYO API key** | Server key (Demo) or session-only user key (BYO)—BYO never persisted to disk |
| **Saved sessions** | Local JSON under `data/sessions/` (gitignored), scoped by usage mode |
| **Developer diagnostics** | Opt-in dev-only sidebar panel (`APP_ENV=dev` + `SHOW_DIAGNOSTICS=true`); no secret values |
| **Dark mode** | Theme toggle with accessible contrast tokens |

---

## AI engineering highlights

| Topic | Implementation |
|-------|----------------|
| **Five prompt strategies** | Zero-shot, few-shot, chain-of-thought, structured JSON output, role-based (`prompts/prompt_strategies.py`) |
| **Mock interview FSM** | Deterministic turn classification and evaluation gating (`mock_interview_flow.py`) |
| **CV extraction & prep** | Two-pass structured JSON with Pydantic models and delimiter-safe CV fencing (`cv/`) |
| **Guardrails** | Input/output pipeline: length limits, redaction, injection heuristics, moderation, rate limits (`security/`) |
| **Retry / backoff** | OpenAI SDK retries for transient errors (`OPENAI_MAX_RETRIES`, exponential backoff) |
| **Usage / cost visibility** | Token counts, latency, and rough USD estimates on LLM responses (`usage_formatting.py`) |
| **Deterministic evaluations** | Fixture-driven task checks without live OpenAI (`evaluations/`, `tests/evaluations/`) |
| **CI** | GitHub Actions: pytest, evaluations, ruff, black—no secrets required (`.github/workflows/ci.yml`) |

---

## Architecture (summary)

Thin **Streamlit UI** → **services** → **OpenAI client**, with prompts and security at the boundaries:

1. **Entry:** `streamlit_app.py` — adds `src/` to `sys.path`, loads optional `.env`, runs `interview_app.app.main.run()`.
2. **App:** `app/main.py`, `controls.py`, `layout.py` — sidebar config and four workspace tabs.
3. **Services:** `interview_generator`, `answer_evaluator`, `chat_service`, `cv_interview_service`.
4. **Security:** `security/pipeline.py` on inputs and outputs before/after LLM calls.
5. **Persistence:** `storage/sessions.py` for mock-interview JSON.

Deeper diagrams: **[docs/architecture.md](docs/architecture.md)**.

---

## Tech stack

- Python **3.11+**
- Streamlit, OpenAI Python SDK v1+, Pydantic / pydantic-settings
- langdetect, pypdf, python-docx
- Dev: pytest, ruff, black, mypy

---

## Setup (local)

```bash
git clone <your-repo-url>
cd AI-Interview-Preparation-Assistant
python3 -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
cp .env.example .env               # Windows: copy .env.example .env
```

Edit `.env` and set `OPENAI_API_KEY` for **Demo mode** (or use **BYO** in the UI without a server key).

```bash
python -m streamlit run streamlit_app.py
```

Open `http://localhost:8501`. To show Developer diagnostics locally, set `SHOW_DIAGNOSTICS=true` in `.env` (requires `APP_ENV=dev`).

---

## Tests and quality

```bash
pytest
pytest tests/evaluations -v
ruff check src tests evaluations
black --check src tests evaluations
```

- Integration smoke (`tests/integration/`) **skips** without `OPENAI_API_KEY`.
- Evaluations use mocked LLM output only — see **[evaluations/README.md](evaluations/README.md)**.

CI runs the same checks on every push and PR (no repository secrets).

---

## Deploy on Streamlit Community Cloud

| Setting | Value |
|---------|--------|
| **Main file** | `streamlit_app.py` |
| **Python** | 3.11 or 3.12 |
| **Dependencies** | `requirements.txt` (runtime only) |

### Steps

1. Push this repo to **GitHub**.
2. Go to [share.streamlit.io](https://share.streamlit.io) → **Create app** → select the repo and branch.
3. Set main file path to **`streamlit_app.py`**.
4. Under **Secrets**, add:

   ```toml
   OPENAI_API_KEY = "sk-your-key-here"
   ```

5. **Deploy**, then run the demo smoke test below on all four tabs.

Full checklist: **[docs/STREAMLIT_CLOUD.md](docs/STREAMLIT_CLOUD.md)**.

### Post-deploy demo (smoke test)

1. **Session setup:** Demo mode → **Apply usage mode** (if prompted).
2. **Mock Interview:** “Let’s start” → answer one question → confirm score-style feedback and follow-up.
3. **Interview Questions:** Generate 3 questions with your sidebar role/focus.
4. **CV Interview Prep:** Upload a short synthetic CV (PDF/DOCX) → run analysis (practice or full prep).
5. **Feedback / Evaluation:** Paste a sample answer → run evaluation.

For reviewers without Cloud access: use **BYO** in the sidebar with your own key (session-only, never saved to git).

---

## Screenshots

_Placeholder — add images under `docs/screenshots/` after deployment and link them here._

Suggested: workspace overview, mock interview feedback, strategy comparison, CV prep, diagnostics panel.

---

## Session modes (Demo vs BYO)

| Mode | API key source |
|------|----------------|
| **Demo** | Server `OPENAI_API_KEY` from `.env` or Streamlit Cloud secrets |
| **BYO** | User enters key in UI; stored only in server `session_state` for that browser session |

BYO keys are **not** written to session JSON or git. **Apply usage mode** resets workspace state when switching modes.

---

## Environment variables

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Required for Demo mode LLM calls |
| `OPENAI_MODEL` | Default preset or raw model id (default: `gpt-4o-mini`) |
| `OPENAI_MAX_RETRIES` | Transient API retries (default: `3`) |
| `APP_ENV` | Environment label (`dev`, `prod`, `test`) |
| `SHOW_DIAGNOSTICS` | Set `true` with `APP_ENV=dev` to show Developer diagnostics in the sidebar (local only) |
| `SESSIONS_DIR` | Saved sessions directory (default: `data/sessions`) |

Security toggles use the `SECURITY_` prefix — see **[docs/security.md](docs/security.md)** and `.env.example`.

---

## Project structure

```
├── streamlit_app.py          # Streamlit Community Cloud entrypoint
├── requirements.txt          # Runtime deps (Cloud)
├── requirements-dev.txt      # Local dev + CI
├── .env.example              # Documented env vars (no secrets)
├── data/sessions/.gitkeep    # Sessions dir tracked; JSON gitignored
├── evaluations/              # Deterministic eval fixtures + checks
├── docs/                     # architecture, security, deployment, Cloud guide
└── src/interview_app/        # Application package
```

---

## Security overview

User text passes through validation, redaction, injection heuristics, optional moderation, and rate limiting before the LLM; outputs are checked afterward. Suitable for a **trusted demo** deployment—not a substitute for multi-tenant auth.

Details: **[docs/security.md](docs/security.md)**.

---

## Limitations

- **Single-user demo:** No accounts, centralized billing, or cross-user isolation beyond session state.
- **Heuristic guardrails:** Novel prompt-injection attacks may bypass rules; optional LLM classifier is reserved, not enabled.
- **Ephemeral Cloud storage:** Saved sessions on Streamlit Community Cloud may not survive redeploys without external storage.
- **English-first UI:** Prompt language is configurable; UI copy is primarily English.
- **Live LLM quality:** Not scored in CI; deterministic evaluations check shape and routing only.

---

## Roadmap

- [ ] Publish **live demo URL** on Streamlit Community Cloud
- [ ] Add README screenshots after deployment
- [ ] Optional **Streamlit in Snowflake** or external analytics (see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md))
- [ ] Multi-user backend with auth and centralized rate limits (out of scope for current Streamlit-only app)
- [ ] OpenTelemetry or export metrics for production monitoring

---

## Additional documentation

| Doc | Content |
|-----|---------|
| [docs/STREAMLIT_CLOUD.md](docs/STREAMLIT_CLOUD.md) | Community Cloud deploy checklist |
| [docs/architecture.md](docs/architecture.md) | Layers and data flow |
| [docs/development.md](docs/development.md) | Conventions and CI |
| [docs/testing.md](docs/testing.md) | Pytest and manual guardrail checks |
| [docs/security.md](docs/security.md) | Guardrails configuration |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Docker and other clouds |
| [evaluations/README.md](evaluations/README.md) | Deterministic evaluation suite |

---

## License / author

See `pyproject.toml` for metadata. Keep `.env`, `.streamlit/secrets.toml`, and `data/sessions/*.json` out of version control (see `.gitignore`).
