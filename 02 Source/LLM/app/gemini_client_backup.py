import os

from google import genai
from google.genai import types


# Use this model unless GEMINI_MODEL overrides it in the environment.
DEFAULT_MODEL = "gemini-2.5-flash"

# Google Search is a Gemini-managed built-in tool. Application function tools
# are supplied separately by the master router for each request.
google_search = types.Tool(google_search=types.GoogleSearch())


class GeminiError(RuntimeError):
    """Raised when Gemini cannot generate a usable reply."""


class GeminiConfigurationError(GeminiError):
    """Raised when required Gemini configuration is missing."""


async def generate_response(
    contents: list[dict[str, object] | types.Content],
    system_instruction: str,
    tools: list[types.Tool] | None = None,
) -> types.GenerateContentResponse:
    """Call Gemini and return the complete response object."""
    # Read credentials at request time so missing configuration produces a clear
    # service error and environment changes do not require importing again.
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise GeminiConfigurationError("GEMINI_API_KEY is not configured.")

    # Allow deployments to select a model without changing source code.
    model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)

    # Gemini 2.5 cannot combine built-in Google Search with custom function
    # declarations. Use the router's custom tools when present; otherwise keep
    # Google Search available for ordinary chat requests.
    request_tools = tools if tools else [google_search]

    try:
        # The async client prevents the FastAPI event loop from blocking while
        # Gemini processes the request.
        async with genai.Client(api_key=api_key).aio as client:
            # Pass conversation context and system instructions unchanged from
            # the router. The router manually executes any requested functions.
            return await client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=request_tools,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True,
                    ),
                    temperature=0.7,
                    max_output_tokens=1_024,
                ),
            )
    except Exception as exc:
        # Convert SDK/network errors into the stable application exception that
        # the FastAPI layer already maps to an HTTP 502 response.
        raise GeminiError("Gemini request failed.") from exc
