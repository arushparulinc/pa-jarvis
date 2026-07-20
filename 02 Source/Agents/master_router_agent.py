import asyncio
from pathlib import Path

from LLM import GeminiConfigurationError, GeminiError, generate_response
from Tools import tool_execution, tool_registry
from google.genai import types


# Resolve the instruction file from this script's location so startup does not
# depend on the directory from which FastAPI was launched.
SOURCE_ROOT = Path(__file__).resolve().parents[1]
SYSTEM_INSTRUCTION_PATH = SOURCE_ROOT / "LLM" / "Gemini_System_Instructions.txt"
SYSTEM_INSTRUCTION = SYSTEM_INSTRUCTION_PATH.read_text(encoding="utf-8").strip()

# The router owns conversation context and serializes turns so user/model pairs
# remain correctly ordered when multiple requests arrive at the same time.
chat_history: list[dict[str, object] | types.Content] = []
chat_history_lock = asyncio.Lock()

# Stop Gemini from entering an endless tool-calling loop.
MAX_TOOL_ROUNDS = 10


async def route_chat_message(message: str) -> str:
    """Route a message, preserve model parts, and return displayable text."""
    # Convert the incoming API string to Gemini's conversation-message format.
    user_message = {
        "role": "user",
        "parts": [{"text": message}],
    }

    # Hold the lock for the complete turn so concurrent requests cannot mix
    # their user messages, tool results, and final model responses.
    async with chat_history_lock:
        # Remember where this turn begins so partial history can be rolled back.
        turn_start = len(chat_history)
        chat_history.append(user_message)

        try:
            # Each iteration asks Gemini what to do next. It either returns a
            # final text response or one or more function calls to execute.
            for tool_round in range(MAX_TOOL_ROUNDS + 1):
                response = await generate_response(
                    contents=chat_history,
                    system_instruction=SYSTEM_INSTRUCTION,
                    tools=tool_registry.get_all_tools(),
                )

                # Preserve Gemini's complete model parts, including function
                # calls and metadata required for subsequent tool rounds.
                response_parts = response.parts or []
                if response_parts:
                    chat_history.append(
                        types.Content(role="model", parts=response_parts)
                    )

                function_calls = response.function_calls or []

                # No requested functions means the model has finished. Extract
                # the user-facing text that FastAPI will return to the frontend.
                if not function_calls:
                    reply = response.text.strip() if response.text else ""
                    if not reply:
                        raise GeminiError("Gemini returned no final text response.")
                    break

                # Permit at most MAX_TOOL_ROUNDS executions, while allowing one
                # additional LLM request to produce the final answer.
                if tool_round == MAX_TOOL_ROUNDS:
                    raise GeminiError(
                        f"Gemini exceeded the limit of {MAX_TOOL_ROUNDS} tool rounds."
                    )

                # Execute every requested function through the central registry
                # and convert each result into Gemini's response format.
                tool_response_parts = []
                for function_call in function_calls:
                    tool_name = function_call.name or ""
                    try:
                        result = tool_execution.execute_tool(
                            tool_name,
                            function_call.args,
                        )
                        tool_result = {"result": result}
                    except Exception as exc:
                        tool_result = {"error": str(exc)}

                    tool_response_parts.append(
                        types.Part.from_function_response(
                            name=tool_name or "unknown_tool",
                            response=tool_result,
                        )
                    )

                chat_history.append(
                    types.Content(role="tool", parts=tool_response_parts)
                )
        except Exception:
            # Do not leave incomplete model/tool messages in shared history when
            # any part of the current turn fails.
            del chat_history[turn_start:]
            raise

    # Only the final text leaves the router; structured context remains here for
    # the next conversation turn.
    return reply
