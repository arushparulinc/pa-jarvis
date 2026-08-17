from . import call_llm, call_tools
from .call_storage import log_event_pgsql


MAX_TOOL_ROUNDS = 10


class SubAgentError(RuntimeError):
    """Raised when a sub-agent cannot produce a final response."""


async def run_sub_agent(
    request_id: str,
    original_user_prompt: str,
    calling_agent: str,
    script_name: str,
) -> str:
    """Run one stateless sub-agent with its own temporary chat history."""
    chat_history: list[dict[str, object]] = [
        {"role": "user", "content": original_user_prompt}
    ]
    provider = "qwen"
    provider_tool_round = 0
    qwen_error: Exception | None = None

    while True:
        try:
            await log_event_pgsql(
                request_id=request_id,
                chat_message=original_user_prompt,
                service_name="agents",
                script_name=script_name,
                event_type="call_llm_wrapper",
                chat_history=chat_history,
            )
            assistant_reply, tool_calls = await call_llm.invoke_llm(
                request_id,
                provider,
                chat_history,
                calling_agent,
            )

            if not tool_calls:
                if not assistant_reply:
                    raise call_llm.LLMServiceError(
                        f"{provider.title()} returned no final text response."
                    )
                chat_history.append(
                    {"role": "assistant", "content": assistant_reply}
                )
                return assistant_reply

            if provider_tool_round == MAX_TOOL_ROUNDS:
                raise call_llm.LLMServiceError(
                    f"{calling_agent} exceeded the limit of "
                    f"{MAX_TOOL_ROUNDS} tool rounds."
                )
            provider_tool_round += 1

            chat_history.append(
                {
                    "role": "assistant",
                    "content": assistant_reply,
                    "tool_calls": tool_calls,
                }
            )

            for tool_call in tool_calls:
                tool_name = str(tool_call["name"])
                arguments = tool_call.get("arguments", {})
                try:
                    await log_event_pgsql(
                        request_id=request_id,
                        chat_message=f"Tool {tool_name}: {arguments}",
                        service_name="agents",
                        script_name=script_name,
                        event_type="call_tools_wrapper",
                        chat_history=chat_history,
                    )
                    result = await call_tools.execute_tool(
                        request_id=request_id,
                        name=tool_name,
                        arguments=arguments,
                        chat_history=chat_history,
                        calling_agent=calling_agent,
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
                qwen_error = llm_error
                provider = "gemini"
                provider_tool_round = 0
                continue

            raise SubAgentError(
                f"{calling_agent} could not generate a response. "
                f"Primary provider error: {qwen_error}. "
                f"Fallback provider error: {llm_error}"
            ) from llm_error
