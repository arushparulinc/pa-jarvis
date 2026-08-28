import asyncio
import logging
from pathlib import Path

from . import call_llm, call_sub_agent
from .call_storage import log_event_pgsql


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
MAX_CHAT_HISTORY_MESSAGES = 10

# Stop a provider from entering an endless tool-calling loop.
MAX_TOOL_ROUNDS = 10


class ChatError(RuntimeError):
    """Raised when no configured chat provider can return a response."""


def _append_chat_history(message: dict[str, object]) -> None:
    """Append one message and retain only valid recent history."""
    chat_history.append(message)
    del chat_history[:-MAX_CHAT_HISTORY_MESSAGES]

    # Do not send history that begins in the middle of an older turn. This
    # also prevents an orphaned tool result after its tool call was trimmed.
    while chat_history and chat_history[0].get("role") != "user":
        del chat_history[0]


async def route_chat_message(request_id: str, message: str) -> str:
    """Manage tool rounds through Qwen first, then fall back to Gemini."""
    # Serialize complete turns so every provider sees a consistent shared
    # history while it is being updated by LLM and tool responses.
    async with chat_history_lock:
        # Keep a snapshot because history trimming can shift list indexes.
        # Restore it if neither provider can complete the current turn.
        previous_history = list(chat_history)
        _append_chat_history({"role": "user", "content": message})

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
                        chat_history=chat_history,
                    )
                    assistant_reply, tool_calls = (
                        await call_llm.invoke_llm(
                            request_id,
                            "qwen",
                            chat_history,
                            "Master Router Agent",
                        )
                    )
                else:
                    await log_event_pgsql(
                        request_id=request_id,
                        chat_message=message,
                        service_name="agents",
                        script_name="master_router_agent.py",
                        event_type="call_llm_wrapper",
                        chat_history=chat_history,
                    )
                    assistant_reply, tool_calls = (
                        await call_llm.invoke_llm(
                            request_id,
                            "gemini",
                            chat_history,
                            "Master Router Agent",
                        )
                    )

                if not tool_calls:
                    if not assistant_reply:
                        error_message = (
                            f"{provider.title()} returned no final text response."
                        )
                        raise call_llm.LLMServiceError(error_message)

                    # Persist the final answer in the same shared context.
                    _append_chat_history(
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
                _append_chat_history(
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
                        arguments = tool_call.get("arguments", {})
                        if not isinstance(arguments, dict):
                            raise ValueError(
                                f"Tool {tool_name} returned invalid arguments."
                            )
                        raw_agent_instructions = arguments.get(
                            "agent_instructions"
                        )
                        if not isinstance(raw_agent_instructions, str):
                            raise ValueError(
                                f"Tool {tool_name} did not provide required "
                                "agent_instructions."
                            )
                        agent_instructions = raw_agent_instructions.strip()
                        if not agent_instructions:
                            raise ValueError(
                                f"Tool {tool_name} provided empty "
                                "agent_instructions."
                            )

                        await log_event_pgsql(
                            request_id=request_id,
                            chat_message=(
                                f"Tool {tool_name}: "
                                f"{arguments}"
                            ),
                            service_name="agents",
                            script_name="master_router_agent.py",
                            event_type="call_sub_agent",
                            chat_history=chat_history,
                        )
                        result = await call_sub_agent.execute_agent_actions(
                            request_id=request_id,
                            agent_name=tool_name,
                            agent_instructions=agent_instructions,
                        )
                        tool_result = {"result": result}
                    except Exception as exc:
                        tool_result = {"error": str(exc)}

                    _append_chat_history(
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

                # Neither provider completed this turn. Restore the history
                # from before the current user message was added.
                chat_history[:] = previous_history
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


