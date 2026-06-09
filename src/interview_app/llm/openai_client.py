"""OpenAI SDK adapter: single entry point for chat completions from services.

Isolates OpenAI-specific types and request shaping. Callers use
``LLMClient.generate_response`` and receive ``LLMResponse`` (see ``utils.types``).

Each successful or failed call writes a **structured audit log** (model, latency,
token counts, route label)—never full prompt text. Fits between ``services/`` and
the external OpenAI HTTP API.

Raises:
    ValueError: If no API key can be resolved from settings or constructor args.

Retries:
    Transient OpenAI failures (429, 5xx, timeouts, connection errors) are retried by the
    official SDK using exponential backoff with jitter. Configure ``OPENAI_MAX_RETRIES``.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError

from interview_app.config.settings import Settings, get_settings
from interview_app.llm.model_settings import (
    MODEL_PRESETS,
    ModelConfig,
    is_model_preset_key,
    resolve_openai_model_id,
)
from interview_app.utils.types import LLMResponse, LLMUsage

logger = logging.getLogger("interview_app.llm")

_RETRYABLE_STATUS_CODES = frozenset({408, 409, 429, 500, 502, 503, 504})


def is_retryable_openai_error(exc: BaseException) -> bool:
    """
    Whether the OpenAI Python SDK will retry this error when ``max_retries`` > 0.

    Mirrors SDK behavior (connection errors, timeouts, 408/409/429, and 5xx).
    Used for tests and logging; retries are delegated to the SDK client.
    """
    if isinstance(exc, (APIConnectionError, APITimeoutError, RateLimitError)):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code in _RETRYABLE_STATUS_CODES
    return False


@dataclass(frozen=True)
class ClientParams:
    """Resolved parameters for a single OpenAI request (after defaults are applied)."""

    model: str
    temperature: float
    top_p: float | None
    max_tokens: int | None


@dataclass
class LLMStream:
    """
    Iterable assistant text stream from ``LLMClient.stream_response``.

    Consume via ``for chunk in stream`` (or ``st.write_stream(stream)``), then read
    ``stream.response`` for the aggregated ``LLMResponse`` (latency always set;
    token usage when the API provides it).
    """

    _chunks: list[str] = field(default_factory=list, repr=False)
    _response: LLMResponse | None = field(default=None, repr=False)
    _completed: bool = field(default=False, repr=False)
    _error: BaseException | None = field(default=None, repr=False)

    def __iter__(self) -> Iterator[str]:
        if self._completed:
            return iter(())
        return self._consume()

    def _consume(self) -> Iterator[str]:
        try:
            yield from self._produce()
        except BaseException as exc:
            self._error = exc
            self._completed = True
            raise
        finally:
            if not self._completed:
                self._completed = True

    def _produce(self) -> Iterator[str]:
        raise NotImplementedError

    @property
    def response(self) -> LLMResponse:
        if not self._completed:
            raise RuntimeError("Stream not finished; consume all chunks before reading response.")
        if self._error is not None:
            raise self._error
        if self._response is None:
            raise RuntimeError("Stream completed without a response.")
        return self._response

    @property
    def completed(self) -> bool:
        return self._completed


def _log_llm_audit(
    *,
    llm_route: str | None,
    model: str,
    success: bool,
    latency_ms: float,
    usage: LLMUsage | None,
    error_type: str | None = None,
) -> None:
    """Structured boundary log: model, tokens, latency, outcome. Never logs prompt text."""
    entry: dict[str, Any] = {
        "event": "llm_call",
        "route": llm_route or "unknown",
        "model": model,
        "success": success,
        "latency_ms": round(latency_ms, 2),
    }
    if usage is not None:
        entry["prompt_tokens"] = usage.prompt_tokens
        entry["completion_tokens"] = usage.completion_tokens
        entry["total_tokens"] = usage.total_tokens
    if error_type:
        entry["error_type"] = error_type

    if success:
        logger.info("LLM %s", entry)
    else:
        logger.warning("LLM %s", entry)


class LLMClient:
    """
    Thin wrapper around the OpenAI Python SDK (v1+).

    This keeps OpenAI-specific details isolated so the rest of the app can call
    `generate_response(system_prompt, user_prompt)` and receive a structured response.
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int | None = None,
        timeout_s: float | None = 60.0,
    ) -> None:
        """
        Create an OpenAI client with reasonable defaults.

        Resolution order:
        - explicit constructor args (model/temperature/…)
        - matching preset defaults (if `Settings.openai_model` is a preset key)
        - fallback to raw `Settings` values
        """
        self._settings = settings or get_settings()

        resolved_key = api_key or (
            self._settings.openai_api_key.get_secret_value()
            if self._settings.openai_api_key is not None
            else None
        )
        if not (resolved_key and str(resolved_key).strip()):
            raise ValueError(
                "OpenAI API key is missing. Set OPENAI_API_KEY in a .env file (copy .env.example to .env) "
                "or as an environment variable. Do not commit .env to version control."
            )
        self._client = OpenAI(
            api_key=resolved_key.strip(),
            max_retries=self._settings.openai_max_retries,
        )
        self._timeout_s = timeout_s

        # Resolve default model: explicit ctor arg > env OPENAI_MODEL (preset key or raw id).
        env_model = self._settings.openai_model
        env_preset: ModelConfig | None = (
            MODEL_PRESETS.get(env_model) if is_model_preset_key(env_model) else None
        )
        fallback_model = resolve_openai_model_id(env_model)
        chosen_raw = model if model is not None else fallback_model
        chosen_preset: ModelConfig | None = (
            MODEL_PRESETS.get(chosen_raw) if is_model_preset_key(chosen_raw) else None
        )
        preset_for_defaults = chosen_preset or env_preset
        self._defaults = ClientParams(
            model=resolve_openai_model_id(chosen_raw),
            temperature=(
                temperature
                if temperature is not None
                else (
                    preset_for_defaults.default_temperature
                    if preset_for_defaults
                    else self._settings.openai_temperature
                )
            ),
            top_p=(
                top_p
                if top_p is not None
                else (preset_for_defaults.default_top_p if preset_for_defaults else None)
            ),
            max_tokens=(
                max_tokens
                if max_tokens is not None
                else (preset_for_defaults.default_max_tokens if preset_for_defaults else None)
            ),
        )

    def generate_response(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int | None = None,
        extra_messages: list[dict[str, Any]] | None = None,
        llm_route: str | None = None,
    ) -> LLMResponse:
        """
        Generate a single assistant response from system + user prompts.

        `extra_messages` can be used to pass additional chat turns in OpenAI's
        `{role, content}` shape, e.g. prior user/assistant messages.

        `llm_route` identifies the call site for audit logs (e.g. ``interview_generator``).
        """
        call_model = resolve_openai_model_id(model) if model is not None else self._defaults.model
        resolved = ClientParams(
            model=call_model,
            temperature=temperature if temperature is not None else self._defaults.temperature,
            top_p=top_p if top_p is not None else self._defaults.top_p,
            max_tokens=max_tokens if max_tokens is not None else self._defaults.max_tokens,
        )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if extra_messages:
            # Insert extra messages between system and the final user prompt.
            messages = messages[:-1] + extra_messages + messages[-1:]

        t0 = time.monotonic()
        try:
            # Single-shot Chat Completions call (kept intentionally simple for this project).
            resp = self._client.chat.completions.create(
                model=resolved.model,
                messages=messages,
                temperature=resolved.temperature,
                top_p=resolved.top_p,
                max_tokens=resolved.max_tokens,
                timeout=self._timeout_s,
            )
        except Exception as exc:
            latency_ms = (time.monotonic() - t0) * 1000.0
            _log_llm_audit(
                llm_route=llm_route,
                model=resolved.model,
                success=False,
                latency_ms=latency_ms,
                usage=None,
                error_type=type(exc).__name__,
            )
            raise

        latency_ms = (time.monotonic() - t0) * 1000.0
        text = (resp.choices[0].message.content or "").strip() if resp.choices else ""
        usage = (
            LLMUsage(
                prompt_tokens=getattr(resp.usage, "prompt_tokens", None),
                completion_tokens=getattr(resp.usage, "completion_tokens", None),
                total_tokens=getattr(resp.usage, "total_tokens", None),
            )
            if getattr(resp, "usage", None) is not None
            else None
        )

        _log_llm_audit(
            llm_route=llm_route,
            model=getattr(resp, "model", resolved.model),
            success=True,
            latency_ms=latency_ms,
            usage=usage,
        )

        return LLMResponse(
            text=text,
            model=getattr(resp, "model", resolved.model),
            usage=usage,
            raw_response_id=getattr(resp, "id", None),
            latency_ms=latency_ms,
            provider="openai",
        )

    def stream_response(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int | None = None,
        extra_messages: list[dict[str, Any]] | None = None,
        llm_route: str | None = None,
    ) -> LLMStream:
        """
        Stream assistant text deltas; aggregate into ``LLMStream.response`` after iteration.

        Token usage is included when the API exposes it on the final stream chunk;
        otherwise ``response.usage`` is ``None`` and latency is still recorded.
        """
        call_model = resolve_openai_model_id(model) if model is not None else self._defaults.model
        resolved = ClientParams(
            model=call_model,
            temperature=temperature if temperature is not None else self._defaults.temperature,
            top_p=top_p if top_p is not None else self._defaults.top_p,
            max_tokens=max_tokens if max_tokens is not None else self._defaults.max_tokens,
        )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if extra_messages:
            messages = messages[:-1] + extra_messages + messages[-1:]

        client = self._client
        timeout_s = self._timeout_s

        class _OpenAIStream(LLMStream):
            def _produce(self) -> Iterator[str]:
                t0 = time.monotonic()
                raw_response_id: str | None = None
                resp_model = resolved.model
                usage: LLMUsage | None = None
                try:
                    stream = client.chat.completions.create(
                        model=resolved.model,
                        messages=messages,
                        temperature=resolved.temperature,
                        top_p=resolved.top_p,
                        max_tokens=resolved.max_tokens,
                        timeout=timeout_s,
                        stream=True,
                        stream_options={"include_usage": True},
                    )
                    for event in stream:
                        if getattr(event, "id", None):
                            raw_response_id = event.id
                        if getattr(event, "model", None):
                            resp_model = event.model
                        event_usage = getattr(event, "usage", None)
                        if event_usage is not None:
                            usage = LLMUsage(
                                prompt_tokens=getattr(event_usage, "prompt_tokens", None),
                                completion_tokens=getattr(event_usage, "completion_tokens", None),
                                total_tokens=getattr(event_usage, "total_tokens", None),
                            )
                        if not event.choices:
                            continue
                        delta = event.choices[0].delta.content or ""
                        if delta:
                            self._chunks.append(delta)
                            yield delta
                except Exception as exc:
                    latency_ms = (time.monotonic() - t0) * 1000.0
                    _log_llm_audit(
                        llm_route=llm_route,
                        model=resolved.model,
                        success=False,
                        latency_ms=latency_ms,
                        usage=None,
                        error_type=type(exc).__name__,
                    )
                    raise

                latency_ms = (time.monotonic() - t0) * 1000.0
                text = "".join(self._chunks).strip()
                self._response = LLMResponse(
                    text=text,
                    model=resp_model,
                    usage=usage,
                    raw_response_id=raw_response_id,
                    latency_ms=latency_ms,
                    provider="openai",
                )
                self._completed = True
                _log_llm_audit(
                    llm_route=llm_route,
                    model=resp_model,
                    success=True,
                    latency_ms=latency_ms,
                    usage=usage,
                )

        return _OpenAIStream()
