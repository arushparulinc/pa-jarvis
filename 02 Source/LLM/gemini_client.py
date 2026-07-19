import asyncio
import os
from pathlib import Path

from google import genai
from google.genai import types


DEFAULT_MODEL = "gemini-2.5-flash"

SYSTEM_INSTRUCTION_PATH = Path(__file__).with_name("Gemini_System_Instructions.txt")
SYSTEM_INSTRUCTION = SYSTEM_INSTRUCTION_PATH.read_text(encoding="utf-8").strip()

google_search = types.Tool(google_search=types.GoogleSearch())

# Gemini expects the value passed to `contents` to be an ordered list. Keeping
# that list in a dictionary leaves room for conversation-level metadata later.
chat_history: dict[str, list[dict[str, object]]] = {"messages": []}
chat_history_lock = asyncio.Lock()


class GeminiError(RuntimeError):
    """Raised when Gemini cannot generate a usable reply."""


class GeminiConfigurationError(GeminiError):
    """Raised when required Gemini configuration is missing."""


async def generate_reply(message: str) -> str:
    """Append a turn to the history and generate the next Gemini response."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise GeminiConfigurationError("GEMINI_API_KEY is not configured.")

    model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    user_message = {
        "role": "user",
        "parts": [{"text": message}],
    }

    # Keep each user/model pair together when requests arrive concurrently.
    async with chat_history_lock:
        chat_history["messages"].append(user_message)

        try:
            async with genai.Client(api_key=api_key).aio as client:
                response = await client.models.generate_content(
                    model=model,
                    contents=chat_history["messages"],
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        tools=[google_search],
                        temperature=0.7,
                        max_output_tokens=1_024,
                    ),
                )

            reply = response.text
            if not reply or not reply.strip():
                raise GeminiError("Gemini returned an empty response.")
        except GeminiError:
            chat_history["messages"].pop()
            raise
        except Exception as exc:
            chat_history["messages"].pop()
            raise GeminiError("Gemini request failed.") from exc

        clean_reply = reply.strip()
        chat_history["messages"].append(
            {
                "role": "model",
                "parts": [{"text": clean_reply}],
            }
        )

    return clean_reply
