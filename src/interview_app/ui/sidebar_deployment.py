"""Sidebar **Deployment** section: links and checklists for hosting Streamlit apps.

Informational only—no cloud API calls. Rendered from ``controls`` via
``render_sidebar_deployment`` for users who want to deploy the app to Streamlit
Community Cloud, Docker, etc.
"""

from __future__ import annotations

import streamlit as st


def _provider_expander(
    *,
    title: str,
    description: str,
    url: str,
    link_label: str,
    steps: list[str],
) -> None:
    """One provider: nested expander with description, link, and steps."""
    with st.expander(title, expanded=False):
        st.markdown(description)
        st.link_button(link_label, url, use_container_width=True)
        st.markdown("**Steps**")
        for i, step in enumerate(steps, start=1):
            st.markdown(f"{i}. {step}")


def render_sidebar_deployment_content() -> None:
    """Deployment guidance for operators (no section chrome — use inside an expander)."""
    st.info(
        "**Before deploying:**  \n"
        "- Push your project to GitHub  \n"
        "- Ensure requirements.txt is up to date  \n"
        "- Store API keys as environment variables  \n"
        "- Do NOT commit session data to Git  \n"
        "- Make sure the app runs locally"
    )

    _provider_expander(
        title="Streamlit Community Cloud",
        description="Easiest way to deploy a Streamlit app directly from GitHub.",
        url="https://share.streamlit.io",
        link_label="Open Streamlit Community Cloud",
        steps=[
            "Push project to GitHub",
            "Go to https://share.streamlit.io",
            "Connect repository",
            "Select app file",
            "Add API key in Secrets",
            "Deploy",
        ],
    )

    _provider_expander(
        title="Azure App Service",
        description="Run the app as a managed Python web app with GitHub deployment.",
        url="https://azure.microsoft.com/products/app-service/",
        link_label="Open Azure App Service",
        steps=[
            "Create an Azure App Service (Python)",
            "Connect your GitHub repository",
            "Set environment variables (OPENAI_API_KEY)",
            "Configure startup command: streamlit run app.py",
            "Deploy",
        ],
    )

    _provider_expander(
        title="AWS (EC2 or Elastic Beanstalk)",
        description="Deploy on a VM or managed platform with full control over networking.",
        url="https://aws.amazon.com/elasticbeanstalk/",
        link_label="Open AWS Elastic Beanstalk",
        steps=[
            "Create a Python environment",
            "Upload your project",
            "Install requirements.txt",
            "Set environment variables",
            "Run: streamlit run app.py --server.port 8080",
            "Open the public URL",
        ],
    )

    _provider_expander(
        title="Google Cloud Run",
        description="Ship a container to a serverless service that scales with traffic.",
        url="https://cloud.google.com/run",
        link_label="Open Google Cloud Run",
        steps=[
            "Create a Dockerfile",
            "Build and push container",
            "Deploy to Cloud Run",
            "Set environment variables",
            "Allow public access",
        ],
    )

    _provider_expander(
        title="Docker",
        description="Package the app once and run it the same way on any Docker host.",
        url="https://docs.docker.com/",
        link_label="Open Docker documentation",
        steps=[
            "Create Dockerfile",
            "Build image",
            "Run container",
            "Expose Streamlit port",
            "Set API keys as environment variables",
        ],
    )


def render_sidebar_deployment() -> None:
    """Legacy entry point — content only; callers should wrap in a collapsed expander."""
    render_sidebar_deployment_content()
