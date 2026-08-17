import os

from google import genai
from google.genai import errors, types

from .call_storage import log_event_pgsql


# Use this model unless GEMINI_MODEL overrides it in the environment.
DEFAULT_MODEL = "gemini-2.5-flash"

class GeminiError(RuntimeError):
    """Raised when Gemini cannot generate a usable reply."""


class GeminiConfigurationError(GeminiError):
    """Raised when required Gemini configuration is missing."""


class GeminiAPIError(GeminiError):
    """Preserve error information returned by the Gemini API."""

    def __init__(
        self,
        message: str,
        status_code: int,
        status: str | None,
        details: object,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.status = status
        self.details = details


async def generate_response(
    request_id: str,
    contents: list[dict[str, object] | types.Content],
    system_instruction: str,
    tools: list[types.Tool],
    chat_history: list[dict[str, object]] | None = None,
) -> types.GenerateContentResponse:
    """Call Gemini and return the complete response object."""
    # Read credentials at request time so missing configuration produces a clear
    # service error and environment changes do not require importing again.
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise GeminiConfigurationError("GEMINI_API_KEY is not configured.")

    # Allow deployments to select a model without changing source code.
    model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)

    try:
        # The async client prevents the FastAPI event loop from blocking while
        # Gemini processes the request.
        async with genai.Client(api_key=api_key).aio as client:
            shared_history = chat_history or []
            chat_message = (
                str(shared_history[-1].get("content", ""))
                if shared_history
                else ""
            )
            await log_event_pgsql(
                request_id=request_id,
                chat_message=chat_message,
                service_name="llm",
                script_name="gemini_client.py",
                event_type="call_gemini_api",
                chat_history=shared_history,
            )
            # Pass conversation context and system instructions unchanged from
            # the router. The router manually executes any requested functions.
            return await client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=tools,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True,
                    ),
                    temperature=0.7,
                    max_output_tokens=1_024,
                ),
            )
    except errors.APIError as exc:
        # Preserve Gemini's HTTP code, status, message, and structured response
        # so the API layer can report errors such as quota exhaustion accurately.
        raise GeminiAPIError(
            message=exc.message or str(exc),
            status_code=exc.code,
            status=exc.status,
            details=exc.details,
        ) from exc
    except Exception as exc:
        # Convert SDK/network errors into the stable application exception that
        # the FastAPI layer already maps to an HTTP 502 response.
        raise GeminiError(
            f"Gemini request failed: {type(exc).__name__}: {exc}"
        ) from exc
