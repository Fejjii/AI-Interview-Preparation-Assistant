# Streamlit Community Cloud deployment

Official flow for hosting this app at [share.streamlit.io](https://share.streamlit.io).

## Repository requirements (verified in this project)

| Check | Status |
|-------|--------|
| Entrypoint | `streamlit_app.py` at repo root |
| Dependencies | `requirements.txt` (runtime only) |
| Secrets in git | None — `.env` and `.streamlit/secrets.toml` are gitignored |
| Sessions dir | `data/sessions/.gitkeep` committed; `data/sessions/*` gitignored |
| `src/` layout | `streamlit_app.py` prepends `src/` to `sys.path` — no extra install step |

## Deploy steps (manual)

1. Push the repository to GitHub.
2. Sign in at [Streamlit Community Cloud](https://share.streamlit.io).
3. **Create app** → connect the GitHub repository.
4. Select the branch to deploy (e.g. `main`).
5. Set **Main file path** to `streamlit_app.py`.
6. Set **Python version** to **3.11** or **3.12** when prompted.
7. Open **Advanced settings** → **Secrets** and add:

   ```toml
   OPENAI_API_KEY = "sk-..."
   ```

   Optional:

   ```toml
   APP_ENV = "prod"
   OPENAI_MAX_RETRIES = "3"
   OPENAI_TRANSCRIPTION_MODEL = "whisper-1"
   SECURITY_MODERATION_ENABLED = "true"
   DEMO_MAX_LLM_CALLS_PER_SESSION = "10"
   ```

   Voice input in **Mock Interview** uses the same `OPENAI_API_KEY` for Demo mode (or the user's BYO key).
   Each transcription counts as **one** demo API call toward `DEMO_MAX_LLM_CALLS_PER_SESSION`.

   Developer diagnostics stay hidden on Cloud (`APP_ENV=prod`). To enable locally,
   set `APP_ENV=dev` and `SHOW_DIAGNOSTICS=true` in `.env`.

8. Click **Deploy** and wait for the build to finish.
9. Open the live URL and run the [post-deploy smoke test](#post-deploy-smoke-test) on all four workspace tabs.

## Required secret names

| Secret / env var | Required | Purpose |
|------------------|----------|---------|
| `OPENAI_API_KEY` | **Yes** (Demo mode on Cloud) | Server-side OpenAI access |

BYO mode still works in the UI without this secret, but portfolio demos typically use Demo mode with a Cloud secret.

## Post-deploy smoke test

1. **Session setup:** Demo mode, apply if needed.
2. **Mock Interview:** Start interview → answer one question → confirm feedback appears.
   Optional: expand **Voice input** → record or upload a short clip → **Transcribe** → edit → **Send transcript**.
3. **Interview Questions:** Generate a small question set.
4. **CV Interview Prep:** Upload a short sample PDF/DOCX (synthetic CV) → run extraction or practice flow.
5. **Feedback / Evaluation:** Submit a sample answer and confirm structured feedback.

## Limitations on Community Cloud

- **Ephemeral filesystem:** Saved sessions under `data/sessions/` may not persist across redeploys or cold starts unless you add external storage later.
- **Single-tenant demo:** Rate limits and guardrails are per Streamlit session, not multi-user auth.
- **No secrets in Diagnostics:** The panel shows configured yes/no only.

## Related docs

- [README.md](../README.md) — setup, tests, portfolio overview
- [DEPLOYMENT.md](DEPLOYMENT.md) — Docker and other clouds
