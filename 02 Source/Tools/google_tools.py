from google.genai import types

from LLM import GeminiError, generate_response


google_search_tool = types.Tool(google_search=types.GoogleSearch())


async def google_search(request: str) -> str:
    """Use a separate Gemini request grounded with Google Search."""
    response = await generate_response(
        contents=[
            {
                "role": "user",
                "parts": [{"text": request}],
            }
        ],
        system_instruction=(
            "Answer the request using Google Search when useful. "
            "Return a concise, factual response."
        ),
        tools=[google_search_tool],
    )

    result = response.text.strip() if response.text else ""
    if not result:
        raise GeminiError("Google Search returned no text response.")

    return result
