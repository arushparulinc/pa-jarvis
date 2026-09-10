import os

from google import genai
from google.genai import errors, types


google_search_tool = types.Tool(google_search=types.GoogleSearch())


class GoogleSearchError(RuntimeError):
    """Raised when the standalone Google Search tool fails."""


async def google_search(request: str) -> str:
    """Use Gemini and its Google Search capability for an internet query."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise GoogleSearchError(
            "GEMINI_API_KEY is not configured for the Tools service."
        )

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    try:
        async with genai.Client(api_key=api_key).aio as client:
            response = await client.models.generate_content(
                model=model,
                contents=request,
                config=types.GenerateContentConfig(
                    system_instruction=(
                        "Answer the request using Google Search when useful. "
                        "Return a concise, factual response."
                    ),
                    tools=[google_search_tool],
                ),
            )
    except errors.APIError as exc:
        raise GoogleSearchError(
            f"Gemini Google Search failed: {exc.message or exc}"
        ) from exc

    result = response.text.strip() if response.text else ""
    if not result:
        raise GoogleSearchError("Google Search returned no text response.")
    return result
