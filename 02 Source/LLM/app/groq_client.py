"""Async client wrapper for Groq's OpenAI-compatible chat API."""

import json
import os
from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from .call_storage import log_llm_call_pgsql, log_service_event_pgsql


GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_TIMEOUT_SECONDS = 180.0


class GroqError(RuntimeError):
    """Raised when Groq cannot generate a usable response."""


class GroqConfigurationError(GroqError):
    """Raised when required Groq configuration is missing."""


class GroqConnectionError(GroqError):
    """Raised when the Groq API cannot be reached."""


class GroqAPIError(GroqError):
    """Preserve an HTTP error returned by Groq."""

    def __init__(self, message: str, status_code: int, details: object) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


async def generate_response(
    request_id: str,
    calling_agent: str,
    messages: Sequence[Mapping[str, Any]],
    system_instruction: str,
    tools: Sequence[Mapping[str, Any]] | None = None,
    chat_history: list[dict[str, object]] | None = None,
) -> dict[str, Any]:
    """Call Groq and return the complete chat-completion response."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise GroqConfigurationError("GROQ_API_KEY is not configured.")

    model = os.getenv("GROQ_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    timeout_seconds = float(
        os.getenv("GROQ_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
    )
    request_messages: list[Mapping[str, Any]] = []
    if system_instruction.strip():
        request_messages.append(
            {"role": "system", "content": system_instruction.strip()}
        )
    request_messages.extend(messages)

    payload: dict[str, object] = {
        "model": model,
        "messages": request_messages,
        "temperature": 0.7,
        "max_completion_tokens": 1_024,
        "stream": False,
    }
    if tools:
        payload["tools"] = list(tools)
        payload["tool_choice"] = "auto"

    shared_history = chat_history or []
    chat_message = (
        str(shared_history[-1].get("content", "")) if shared_history else ""
    )
    message_sent = json.dumps(payload, default=str)

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(
                GROQ_CHAT_COMPLETIONS_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
    except httpx.RequestError as exc:
        error_response = json.dumps(
            {
                "success": False,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            }
        )
        await log_llm_call_pgsql(
            request_id=request_id,
            calling_agent_name=calling_agent,
            message_sent=message_sent,
            message_response=error_response,
        )
        raise GroqConnectionError(f"Could not connect to Groq: {exc}") from exc

    if response.is_error:
        try:
            details: object = response.json()
        except ValueError:
            details = response.text
        await log_llm_call_pgsql(
            request_id=request_id,
            calling_agent_name=calling_agent,
            message_sent=message_sent,
            message_response=json.dumps(
                {
                    "success": False,
                    "status_code": response.status_code,
                    "details": details,
                },
                default=str,
            ),
        )
        raise GroqAPIError(
            message=f"Groq returned HTTP {response.status_code}: {details}",
            status_code=response.status_code,
            details=details,
        )

    try:
        result = response.json()
        if not isinstance(result, dict) or not result.get("choices"):
            raise ValueError("Response contains no choices.")
    except (TypeError, ValueError) as exc:
        await log_llm_call_pgsql(
            request_id=request_id,
            calling_agent_name=calling_agent,
            message_sent=message_sent,
            message_response=json.dumps(
                {
                    "success": False,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "raw_response": response.text,
                }
            ),
        )
        raise GroqError(f"Groq returned an invalid response: {exc}") from exc

    serialized_response = json.dumps(result, default=str)
    await log_llm_call_pgsql(
        request_id=request_id,
        calling_agent_name=calling_agent,
        message_sent=message_sent,
        message_response=serialized_response,
    )
    await log_service_event_pgsql(
        request_id=request_id,
        chat_message=chat_message,
        service_name="llm",
        script_name="groq_client.py",
        event_type="call_groq_api",
        chat_history=[
            *shared_history,
            {"role": "assistant", "content": result},
        ],
    )
    return result
