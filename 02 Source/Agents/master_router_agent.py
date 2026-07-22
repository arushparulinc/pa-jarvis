import asyncio
import json
import logging
from pathlib import Path

from LLM import (
    GeminiAPIError,
    GeminiConfigurationError,
    GeminiError,
    generate_response,
)
from LLM.qwen_client import (
    QwenAPIError,
    QwenConnectionError,
    QwenError,
    generate_response as generate_qwen_response,
)
from Tools import tool_execution, tool_registry
from google.genai import types


# Resolve the instruction file from this script's location so startup does not
# depend on the directory from which FastAPI was launched.
SOURCE_ROOT = Path(__file__).resolve().parents[1]
SYSTEM_INSTRUCTION_PATH = SOURCE_ROOT / "LLM" / "Gemini_System_Instructions.txt"
SYSTEM_INSTRUCTION = SYSTEM_INSTRUCTION_PATH.read_text(encoding="utf-8").strip()

# Write master-router events to a dedicated file beside this module. Avoid
# adding the same handler more than once when Uvicorn reloads the application.
MASTER_AGENT_LOG_PATH = Path(__file__).with_name("master_agent.log")
master_agent_logger = logging.getLogger("pa_jarvis.master_agent")
master_agent_logger.setLevel(logging.INFO)
master_agent_logger.propagate = False

if not any(
    isinstance(handler, logging.FileHandler)
    and Path(handler.baseFilename) == MASTER_AGENT_LOG_PATH
    for handler in master_agent_logger.handlers
):
    master_agent_log_handler = logging.FileHandler(
        MASTER_AGENT_LOG_PATH,
        encoding="utf-8",
    )
    master_agent_log_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s"
        )
    )
    master_agent_logger.addHandler(master_agent_log_handler)

# Keep one provider-neutral history containing only user messages and final
# assistant answers. Provider-specific tool calls remain temporary to a request.
chat_history: list[dict[str, str]] = []
chat_history_lock = asyncio.Lock()

# Stop Gemini from entering an endless tool-calling loop.
MAX_TOOL_ROUNDS = 10


class ChatError(RuntimeError):
    """Raised when no configured chat provider can return a response."""


async def route_chat_message_gemini(message: str) -> str:
    """Translate shared history to Gemini format and generate a reply."""
    gemini_request_history: list[dict[str, object] | types.Content] = [
        {
            "role": "model" if item["role"] == "assistant" else "user",
            "parts": [{"text": item["content"]}],
        }
        for item in chat_history
    ]
    gemini_request_history.append(
        {
            "role": "user",
            "parts": [{"text": message}],
        }
    )

    # Each iteration asks Gemini for either a final answer or tool calls.
    for tool_round in range(MAX_TOOL_ROUNDS + 1):
        response = await generate_response(
            contents=gemini_request_history,
            system_instruction=SYSTEM_INSTRUCTION,
            tools=tool_registry.get_all_gemini_tools(),
        )

        # Keep tool-call parts only in this temporary provider request history.
        response_parts = response.parts or []
        if response_parts:
            gemini_request_history.append(
                types.Content(role="model", parts=response_parts)
            )

        function_calls = response.function_calls or []

        # No function calls means Gemini has produced the final answer.
        if not function_calls:
            gemini_reply = response.text.strip() if response.text else ""
            if not gemini_reply:
                raise GeminiError("Gemini returned no final text response.")
            return gemini_reply

        # Allow one final model request after the maximum tool executions.
        if tool_round == MAX_TOOL_ROUNDS:
            raise GeminiError(
                f"Gemini exceeded the limit of {MAX_TOOL_ROUNDS} tool rounds."
            )

        # Execute requested functions and add their temporary Gemini results.
        tool_response_parts = []
        for function_call in function_calls:
            tool_name = function_call.name or ""
            try:
                result = await tool_execution.execute_tool(
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

        gemini_request_history.append(
            types.Content(role="tool", parts=tool_response_parts)
        )


async def route_chat_message_qwen(message: str) -> str:
    """Translate shared history to Ollama format and generate a Qwen reply."""
    qwen_request_history: list[dict[str, object]] = [
        {
            "role": item["role"],
            "content": item["content"],
        }
        for item in chat_history
    ]
    qwen_request_history.append(
        {
            "role": "user",
            "content": message,
        }
    )

    for tool_round in range(MAX_TOOL_ROUNDS + 1):
        qwen_response = await generate_qwen_response(
            messages=qwen_request_history,
            system_instruction=SYSTEM_INSTRUCTION,
            tools=tool_registry.get_all_ollama_tools(),
        )
        master_agent_logger.info(
            "generate_qwen_response output=%s",
            qwen_response.model_dump_json(exclude_none=True),
        )

        qwen_tool_calls = qwen_response.message.tool_calls or []
        if not qwen_tool_calls:
            qwen_reply = (qwen_response.message.content or "").strip()
            if not qwen_reply:
                raise QwenError("Qwen returned no final text response.")
            return qwen_reply

        if tool_round == MAX_TOOL_ROUNDS:
            raise QwenError(
                f"Qwen exceeded the limit of {MAX_TOOL_ROUNDS} tool rounds."
            )

        # Preserve tool requests locally, but omit Qwen's thinking field.
        qwen_request_history.append(
            {
                "role": "assistant",
                "content": qwen_response.message.content or "",
                "tool_calls": [
                    tool_call.model_dump(exclude_none=True)
                    for tool_call in qwen_tool_calls
                ],
            }
        )

        for qwen_tool_call in qwen_tool_calls:
            tool_name = qwen_tool_call.function.name
            try:
                result = await tool_execution.execute_tool(
                    tool_name,
                    qwen_tool_call.function.arguments,
                )
                tool_result = {"result": result}
            except Exception as exc:
                tool_result = {"error": str(exc)}

            qwen_request_history.append(
                {
                    "role": "tool",
                    "tool_name": tool_name,
                    "content": json.dumps(tool_result, default=str),
                }
            )


async def _try_qwen(message: str) -> str:
    """Call Qwen and translate provider errors to the router boundary."""
    try:
        qwen_route_output = await route_chat_message_qwen(message)
        master_agent_logger.info(
            "route_chat_message_qwen output=%s",
            qwen_route_output,
        )
        return qwen_route_output
    except QwenError as exc:
        raise ChatError(f"Qwen failed: {exc}") from exc


async def _try_gemini(message: str) -> str:
    """Call Gemini and translate provider errors to the router boundary."""
    try:
        return await route_chat_message_gemini(message)
    except GeminiError as exc:
        raise ChatError(f"Gemini failed: {exc}") from exc


async def route_chat_message(message: str) -> str:
    """Route through local Qwen first, then Gemini if Qwen fails."""
    # Serialize complete turns so every provider sees a consistent shared
    # history and the successful user/assistant pair is committed atomically.
    async with chat_history_lock:
        try:
            assistant_reply = await _try_qwen(message)
        except ChatError as qwen_error:
            try:
                assistant_reply = await _try_gemini(message)
            except ChatError as gemini_error:
                raise ChatError(
                    "No chat provider could generate a response. "
                    f"Primary provider error: {qwen_error}. "
                    f"Fallback provider error: {gemini_error}"
                ) from gemini_error

        chat_history.extend(
            [
                {"role": "user", "content": message},
                {"role": "assistant", "content": assistant_reply},
            ]
        )
        return assistant_reply
