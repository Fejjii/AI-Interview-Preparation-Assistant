from __future__ import annotations

"""
Integration smoke test for the OpenAI client.

This test is skipped by default unless `OPENAI_API_KEY` is present, so CI/local runs
won't fail for users who haven't configured credentials.
"""

import os

import pytest

from interview_app.llm.openai_client import LLMClient


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="Set OPENAI_API_KEY to run the OpenAI client smoke test.",
)
def test_llm_client_generate_response_smoke() -> None:
    """Make a minimal API call and assert we got *some* text back."""
    client = LLMClient()
    resp = client.generate_response(
        llm_route="integration_smoke",
        system_prompt="You are a helpful assistant.",
        user_prompt="Reply with exactly: ok",
        max_tokens=10,
        temperature=0.0,
    )
    assert resp.text
