from copy import deepcopy
import os

import httpx

from .call_storage import log_service_event_pgsql


DEFAULT_LLM_SERVICE_URL = "http://127.0.0.1:8002"
DEFAULT_TIMEOUT_SECONDS = 300.0
SUPPORTED_PROVIDERS = {"gemini", "groq", "qwen"}
PROVIDER_ENVIRONMENT = (
    ("PRIMARY_PROVIDER", "gemini"),
    ("SECONDARY_PROVIDER", "groq"),
    ("DEFAULT_PROVIDER", "qwen"),
)


class LLMServiceError(RuntimeError):
    """Raised when the LLM HTTP service cannot complete a request."""


def _provider_order() -> list[str]:
    """Return the validated, de-duplicated provider fallback order."""
    providers: list[str] = []
    for variable_name, fallback in PROVIDER_ENVIRONMENT:
        provider = os.getenv(variable_name, fallback).strip().casefold()
        if provider not in SUPPORTED_PROVIDERS:
            raise LLMServiceError(
                f"{variable_name} contains unsupported provider {provider!r}. "
                f"Expected one of: {', '.join(sorted(SUPPORTED_PROVIDERS))}."
            )
        if provider not in providers:
            providers.append(provider)
    return providers


async def _invoke_provider(
    request_id: str,
    provider: str,
    shared_history: list[dict[str, object]],
    calling_agent: str,
) -> tuple[str, list[dict[str, object]]]:
    """Invoke one provider through the independent LLM service."""
    base_url = os.getenv(
        "LLM_SERVICE_URL",
        DEFAULT_LLM_SERVICE_URL,
    ).rstrip("/")
    timeout = float(
        os.getenv("LLM_SERVICE_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
    )

    try:
        message = (
            str(shared_history[-1].get("content", ""))
            if shared_history
            else ""
        )
        await log_service_event_pgsql(
            request_id=request_id,
            chat_message=message,
            service_name="agents",
            script_name="call_llm.py",
            event_type="call_llm",
            chat_history=shared_history,
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{base_url}/invoke",
                json={
                    "RequestID": request_id,
                    "provider": provider,
                    "shared_history": shared_history,
                    "calling_agent": calling_agent,
                },
            )
    except httpx.RequestError as exc:
        raise LLMServiceError(
            f"Could not connect to the LLM service: {exc}"
        ) from exc

    if response.is_error:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise LLMServiceError(
            f"LLM service returned HTTP {response.status_code}: {detail}"
        )

    try:
        payload = response.json()
        reply = payload["reply"]
        tool_calls = payload["tool_calls"]
    except (ValueError, KeyError, TypeError) as exc:
        raise LLMServiceError("LLM service returned an invalid response.") from exc

    if not isinstance(reply, str) or not isinstance(tool_calls, list):
        raise LLMServiceError("LLM service returned an invalid response shape.")
    if not reply.strip() and not tool_calls:
        raise LLMServiceError("LLM provider returned no text or tool calls.")
    return reply, tool_calls


async def invoke_llm(
    request_id: str,
    shared_history: list[dict[str, object]],
    calling_agent: str,
) -> tuple[str, list[dict[str, object]]]:
    """Try configured providers in order without adding failures to history."""
    clean_history = deepcopy(shared_history)
    failures: list[str] = []

    for provider in _provider_order():
        try:
            return await _invoke_provider(
                request_id=request_id,
                provider=provider,
                shared_history=deepcopy(clean_history),
                calling_agent=calling_agent,
            )
        except LLMServiceError as exc:
            failures.append(f"{provider}: {exc}")

    raise LLMServiceError(
        "All configured LLM providers failed. " + " | ".join(failures)
    )
