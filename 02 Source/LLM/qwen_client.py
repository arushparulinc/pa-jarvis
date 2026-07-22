import os
from collections.abc import Mapping, Sequence
from typing import Any

from ollama import (
    AsyncClient,
    ChatResponse,
    RequestError,
    ResponseError,
    Tool,
)


# Ollama's official Qwen3 8B model tag. Override these values in the environment
# when Ollama runs on another machine or under a different model alias.
DEFAULT_MODEL = "qwen3:4b-instruct"
DEFAULT_HOST = "http://127.0.0.1:11434"
DEFAULT_TIMEOUT_SECONDS = 180.0


class QwenError(RuntimeError):
    """Raised when the local Qwen model cannot generate a response."""


class QwenConnectionError(QwenError):
    """Raised when the request cannot reach the local Ollama service."""


class QwenAPIError(QwenError):
    """Preserve an error response returned by Ollama."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


async def generate_response(
    messages: Sequence[Mapping[str, Any]],
    system_instruction: str,
    tools: Sequence[Mapping[str, Any] | Tool] | None = None,
) -> ChatResponse:
    """Call Qwen3 8B through local Ollama and return the complete response."""
    host = os.getenv("OLLAMA_HOST", DEFAULT_HOST)
    model = os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
    timeout_seconds = float(
        os.getenv("OLLAMA_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
    )

    # Ollama represents system instructions as the first chat message. Copy the
    # caller's history so this client never mutates router-owned context.
    request_messages: list[Mapping[str, Any]] = []
    if system_instruction.strip():
        request_messages.append(
            {
                "role": "system",
                "content": system_instruction.strip(),
            }
        )
    request_messages.extend(messages)

    try:
        response = await AsyncClient(host=host, timeout=timeout_seconds).chat(
            model=model,
            messages=request_messages,
            tools=tools,
            stream=False,
            think=False,
            keep_alive="10m",
            options={
                "temperature": 0.5,
                "num_predict": 256,
            },
        )
    except ResponseError as exc:
        raise QwenAPIError(
            message=str(exc),
            status_code=exc.status_code,
        ) from exc
    except RequestError as exc:
        raise QwenConnectionError(
            f"Could not send the request to Ollama at {host}: {exc}"
        ) from exc
    except Exception as exc:
        raise QwenError(
            f"Qwen request failed: {type(exc).__name__}: {exc}"
        ) from exc

    if not isinstance(response, ChatResponse):
        raise QwenError("Ollama returned an unexpected streaming response.")

    return response
