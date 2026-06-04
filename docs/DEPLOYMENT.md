# Deployment: Docker, cloud, and Snowflake

This doc describes how to run the AI Interview Coach app in production using Docker, a cloud provider, and optional Snowflake.

## Prerequisites

- Docker (and optionally a container registry: Docker Hub, ECR, ACR, GCR).
- An OpenAI API key (and optionally a Snowflake account for data/analytics).

## Streamlit Community Cloud

For the managed Streamlit hosting flow (entrypoint `streamlit_app.py`, secrets, smoke test), see **[STREAMLIT_CLOUD.md](STREAMLIT_CLOUD.md)**.

## Pre-deploy verification (CI parity)

Before shipping, run locally (or rely on GitHub Actions `.github/workflows/ci.yml`):

```bash
pytest
pytest tests/evaluations -v
ruff check src tests evaluations
black --check src tests evaluations
```

No API key is required for CI: the OpenAI integration smoke test skips when `OPENAI_API_KEY` is unset. After deploy, open the sidebar **Diagnostics** expander to confirm environment, model preset, usage mode, and security toggles (no secret values are shown).

## 1. Docker

### Build

From the project root (where `Dockerfile` and `streamlit_app.py` live):

```bash
docker build -t interview-coach:latest .
```

### Run locally

```bash
docker run -p 8501:8501 -e OPENAI_API_KEY=your_openai_key interview-coach:latest
```

Open http://localhost:8501.

### Persist sessions (optional)

Sessions are stored under `data/sessions` by default. To keep them across container restarts, mount a volume:

```bash
docker run -p 8501:8501 \
  -e OPENAI_API_KEY=your_key \
  -v interview-sessions:/app/data \
  interview-coach:latest
```

Or set a custom dir:

```bash
docker run -p 8501:8501 \
  -e OPENAI_API_KEY=your_key \
  -e SESSIONS_DIR=/data/sessions \
  -v my-sessions:/data \
  interview-coach:latest
```

## 2. Cloud provider

Push the image to your registry, then run it on a container service.

### AWS

- **ECS (Fargate)** or **App Runner**: create a task/service from the image, set `OPENAI_API_KEY` in secrets, expose port 8501, attach a volume for `SESSIONS_DIR` if needed.
- **EKS**: deploy as a Deployment with a Service (LoadBalancer or Ingress); use Secrets for env vars.

### Azure

- **Container Apps** or **AKS**: deploy the image, set environment variables (or Key Vault references) for `OPENAI_API_KEY`, mount a volume for session storage if desired.

### GCP

- **Cloud Run**: deploy with `gcloud run deploy --image=... --set-env-vars=OPENAI_API_KEY=...`; use a volume or Cloud Storage for `SESSIONS_DIR` if you need persistence.

In all cases, use the provider’s secret manager for `OPENAI_API_KEY` instead of plain env in the UI.

## 3. Snowflake

### Option A: Streamlit in Snowflake (SiS)

- Use Snowflake’s native Streamlit: develop and run the app inside Snowflake, with data in Snowflake.
- Best when your users and data are already in Snowflake and you want a single platform.
- You would adapt this app’s logic (prompts, services) to run in the Snowflake Streamlit runtime and optionally pull job/role data from Snowflake tables.

### Option B: External app + Snowflake

- Run this app as a Docker container on AWS/Azure/GCP (as above).
- Use **Snowflake Python Connector** or **Snowflake SQL API** from the app to:
  - Write session metadata or usage logs to Snowflake tables.
  - Run analytics or dashboards in Snowflake on top of that data.
- Sessions can stay in the container/volume; Snowflake is used for reporting and integration, not as the primary session store (unless you implement a custom store that writes to Snowflake).

### Summary

| Goal                         | Approach                                      |
|-----------------------------|-----------------------------------------------|
| Run in Docker on your machine | Build + `docker run` with `OPENAI_API_KEY`   |
| Run on AWS/Azure/GCP        | Deploy image to ECS/App Runner, Container Apps, or Cloud Run |
| Use Snowflake for data/UI   | Use Streamlit in Snowflake (SiS) and adapt app |
| Use Snowflake for analytics only | Run app on cloud; sync or log to Snowflake via connector/SQL API |

## 4. Dockerfile

The repo includes a production-oriented `Dockerfile` at the root (non-root user, `pip install .` from `pyproject.toml`, health check). Build and run as in section 1.
