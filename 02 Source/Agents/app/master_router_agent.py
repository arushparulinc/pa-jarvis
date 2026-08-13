import asyncio
import logging
from pathlib import Path

from . import call_llm, call_tools
from .call_storage import log_event_pgsql


# Resolve the instruction file from this script's location so startup does not
# depend on the directory from which FastAPI was launched.
SYSTEM_INSTRUCTION_PATH = Path(__file__).with_name("LLM_System_Instructions.txt")
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

# Keep one provider-neutral history shared by Qwen and Gemini. It contains
# user messages, assistant answers, tool requests, and tool results so either
# provider can continue the complete conversation.
chat_history: list[dict[str, object]] = []
chat_history_lock = asyncio.Lock()

# Stop a provider from entering an endless tool-calling loop.
MAX_TOOL_ROUNDS = 10


class ChatError(RuntimeError):
    """Raised when no configured chat provider can return a response."""


async def route_chat_message(request_id: str, message: str) -> str:
    """Manage tool rounds through Qwen first, then fall back to Gemini."""
    # Serialize complete turns so every provider sees a consistent shared
    # history while it is being updated by LLM and tool responses.
    async with chat_history_lock:
        # Remember where this turn begins so an unsuccessful turn can be
        # removed without affecting context from earlier completed turns.
        turn_start_index = len(chat_history)
        chat_history.append({"role": "user", "content": message})

        provider = "qwen"
        provider_tool_round = 0
        qwen_error: Exception | None = None

        while True:
            try:
                if provider == "qwen":
                    await log_event_pgsql(
                        request_id=request_id,
                        chat_message=message,
                        service_name="agents",
                        script_name="master_router_agent.py",
                        event_type="call_llm_wrapper",
                    )
                    assistant_reply, tool_calls = (
                        await call_llm.invoke_llm(
                            request_id,
                            "qwen",
                            chat_history,
                            SYSTEM_INSTRUCTION,
                        )
                    )
                else:
                    await log_event_pgsql(
                        request_id=request_id,
                        chat_message=message,
                        service_name="agents",
                        script_name="master_router_agent.py",
                        event_type="call_llm_wrapper",
                    )
                    assistant_reply, tool_calls = (
                        await call_llm.invoke_llm(
                            request_id,
                            "gemini",
                            chat_history,
                            SYSTEM_INSTRUCTION,
                        )
                    )

                if not tool_calls:
                    if not assistant_reply:
                        error_message = (
                            f"{provider.title()} returned no final text response."
                        )
                        raise call_llm.LLMServiceError(error_message)

                    # Persist the final answer in the same shared context.
                    chat_history.append(
                        {
                            "role": "assistant",
                            "content": assistant_reply,
                        }
                    )
                    break

                if provider_tool_round == MAX_TOOL_ROUNDS:
                    error_message = (
                        f"{provider.title()} exceeded the limit of "
                        f"{MAX_TOOL_ROUNDS} tool rounds."
                    )
                    raise call_llm.LLMServiceError(error_message)
                provider_tool_round += 1

                # Store the normalized LLM tool request once, regardless of
                # which provider requested it.
                chat_history.append(
                    {
                        "role": "assistant",
                        "content": assistant_reply,
                        "tool_calls": tool_calls,
                    }
                )

                # Execute all normalized tool calls in one shared block.
                for tool_call in tool_calls:
                    tool_name = str(tool_call["name"])
                    try:
                        await log_event_pgsql(
                            request_id=request_id,
                            chat_message=(
                                f"Tool {tool_name}: "
                                f"{tool_call.get('arguments', {})}"
                            ),
                            service_name="agents",
                            script_name="master_router_agent.py",
                            event_type="call_tools_wrapper",
                        )
                        result = await call_tools.execute_tool(
                            request_id,
                            tool_name,
                            tool_call.get("arguments", {}),
                        )
                        tool_result = {"result": result}
                    except Exception as exc:
                        tool_result = {"error": str(exc)}

                    chat_history.append(
                        {
                            "role": "tool",
                            "tool_name": tool_name,
                            "tool_result": tool_result,
                        }
                    )

            except call_llm.LLMServiceError as llm_error:
                if provider == "qwen":
                    # Preserve context and retry through the Gemini provider.
                    qwen_error = llm_error
                    provider = "gemini"
                    provider_tool_round = 0
                    continue

                # Neither provider completed this turn. Roll back only the
                # events added since the current user message.
                del chat_history[turn_start_index:]
                raise ChatError(
                    "No chat provider could generate a response. "
                    f"Primary provider error: {qwen_error}. "
                    f"Fallback provider error: {llm_error}"
                ) from llm_error

        master_agent_logger.info(
            "RequestID=%s route_chat_message output=%s",
            request_id,
            assistant_reply,
        )
        return assistant_reply


