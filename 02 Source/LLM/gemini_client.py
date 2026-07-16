import os

from google import genai
from google.genai import types


DEFAULT_MODEL = "gemini-2.5-flash"
SYSTEM_INSTRUCTION = (
    "Answer clearly, acknowledge uncertainty, and do not invent facts."
)
google_search = types.Tool(google_search=types.GoogleSearch())


class GeminiError(RuntimeError):
    """Raised when Gemini cannot generate a usable reply."""


class GeminiConfigurationError(GeminiError):
    """Raised when required Gemini configuration is missing."""


async def generate_reply(message: str) -> str:
    """Generate one assistant response for a user message using Gemini."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise GeminiConfigurationError("GEMINI_API_KEY is not configured.")

    model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)

    try:
        async with genai.Client(api_key=api_key).aio as client:
            response = await client.models.generate_content(
                model=model,
                contents=message,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    tools=[google_search],
                    temperature=0.7,
                    max_output_tokens=1_024,
                ),
            )
    except Exception as exc:
        raise GeminiError("Gemini request failed.") from exc

    reply = response.text
    if not reply or not reply.strip():
        raise GeminiError("Gemini returned an empty response.")

    return reply.strip()
