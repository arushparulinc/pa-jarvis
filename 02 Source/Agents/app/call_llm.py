import os

import httpx

from .call_storage import log_event_pgsql


DEFAULT_LLM_SERVICE_URL = "http://127.0.0.1:8002"
DEFAULT_TIMEOUT_SECONDS = 300.0


class LLMServiceError(RuntimeError):
    """Raised when the LLM HTTP service cannot complete a request."""


async def invoke_llm(
    request_id: str,
    provider: str,
    shared_history: list[dict[str, object]],
    calling_agent: str,
) -> tuple[str, list[dict[str, object]]]:
    """Invoke Qwen or Gemini through the independent LLM service."""
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
        await log_event_pgsql(
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
    return reply, tool_calls
