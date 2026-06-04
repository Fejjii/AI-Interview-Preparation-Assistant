# Development

Guidelines for running, extending, and maintaining the Interview App locally.

---

## Environment

- **Python 3.11+** (see `requires-python` in `pyproject.toml`).
- Use a **virtual environment** at the project root (e.g. `.venv`).
- Never commit **secrets**: use `.env` locally; `.env.example` documents variables only.

---

## Common commands

### Install dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

Runtime-only install (matches Streamlit Community Cloud): `pip install -r requirements.txt`

### Run the app

```powershell
streamlit run streamlit_app.py
```

Or with Make (Unix/Git Bash): `make run`.

### Tests

```powershell
pytest
pytest tests\unit -v
pytest tests\evaluations -v
```

See [testing.md](testing.md) for integration tests, evaluations, and manual guardrail checks.

### Lint, format, typecheck

```powershell
ruff check src tests evaluations
black --check src tests evaluations
mypy src
```

Or: `make lint`, `make format`, `make typecheck`.

### CI (GitHub Actions)

On every push and pull request, [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs:

- `pytest` (OpenAI smoke test skips without `OPENAI_API_KEY`)
- `pytest tests/evaluations -v`
- `ruff check src tests evaluations`
- `black --check src tests evaluations`

No repository secrets are required for CI.

---

## Project conventions

- **`src/` layout:** Import the package as `interview_app` after `streamlit_app.py` inserts `src/` on `sys.path`.
- **Small, focused modules:** Keep Streamlit-specific code in `app/` and `ui/`; business logic in `services/`.
- **Type hints:** Prefer explicit types on public functions; Pydantic models for structured data crossing boundaries.
- **Errors:** Surface user-safe messages via `utils/errors.py` helpers where appropriate; log security events through `security/logging.py`.

---

## Adding a new prompt strategy

1. Add or adjust content in `prompts/prompt_templates.py` if you need new static blocks.
2. Implement a builder in `prompts/prompt_strategies.py` that returns `PromptBuildResult` (system + user strings).
3. Register the strategy in the strategy dispatch used by `interview_generator` (and any UI selectbox in `app/controls.py`).
4. Add a **unit test** that asserts key phrases or structure in the composed prompts (see existing tests under `tests/unit/test_prompt_strategies.py`).

---

## Adding a new workspace tab or service

1. Extend `WORKSPACE_TAB_LABELS` in `app/ui_settings.py` if you add a primary tab.
2. Render the panel in `app/layout.py` and keep orchestration there or in a small helper module under `app/`.
3. Implement LLM-facing logic in `services/` with `run_input_pipeline` / `run_output_pipeline` around model calls.
4. Add tests under `tests/unit/` for parsing and guardrail behavior.

---

## Debugging

- **Prompt debug:** When enabled in the sidebar, some flows show system/user prompts in the UI (never logged by default in structured audit entries).
- **Guardrail expanders:** The UI can show structured guardrail summaries for failed or flagged requests.
- **Diagnostics panel:** Sidebar expander **Diagnostics** (collapsed by default) shows environment, model preset, usage mode, whether a server `OPENAI_API_KEY` is configured (yes/no only), sessions directory path, security toggles, and evaluation commands. It never displays secret values or makes network calls.
- **Session files:** Inspect JSON under `data/sessions/` (or your `SESSIONS_DIR`) for saved transcripts.

---

## Related docs

- [architecture.md](architecture.md) — layers and data flow.
- [testing.md](testing.md) — pytest and manual checks.
- [security.md](security.md) — guardrails and configuration.
