import json
import logging

from . import qwen_client, system_instructions, tools_registry
from .call_storage import log_event_pgsql


master_agent_logger = logging.getLogger("pa_jarvis.master_agent")


async def route_chat_message_qwen(
    request_id: str,
    shared_history: list[dict[str, object]],
    calling_agent: str,
) -> tuple[str, list[dict[str, object]]]:
    """Make one Qwen request and return provider-neutral output."""
    # Convert the generic registry entries into Ollama tool definitions.
    qwen_tools = []
    for tool in tools_registry.get_all_tools(calling_agent):
        parameters = tool["parameters"]
        parameter_schema: dict[str, object] = {
            "type": "object",
            "properties": {
                parameter["name"]: {
                    "type": parameter["type"],
                    "description": parameter["description"],
                }
                for parameter in parameters
            },
        }
        required = [
            parameter["name"]
            for parameter in parameters
            if parameter.get("required")
        ]
        if required:
            parameter_schema["required"] = required

        qwen_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": parameter_schema,
                },
            }
        )

    # Convert the shared provider-neutral history into Ollama messages.
    qwen_history = []
    for item in shared_history:
        qwen_item: dict[str, object] = {
            "role": item["role"],
            "content": item.get("content", ""),
        }
        if item["role"] == "assistant" and item.get("tool_calls"):
            qwen_item["tool_calls"] = [
                {
                    "function": {
                        "name": tool_call["name"],
                        "arguments": tool_call.get("arguments", {}),
                    }
                }
                for tool_call in item["tool_calls"]
            ]
        elif item["role"] == "tool":
            qwen_item["tool_name"] = item["tool_name"]
            qwen_item["content"] = json.dumps(
                item["tool_result"],
                default=str,
            )
        qwen_history.append(qwen_item)

    system_instruction = system_instructions.get_system_instructions(
        calling_agent
    )
    chat_message = (
        str(shared_history[-1].get("content", ""))
        if shared_history
        else ""
    )
    await log_event_pgsql(
        request_id=request_id,
        chat_message=chat_message,
        service_name="llm",
        script_name="qwen_chat.py",
        event_type="call_qwen_client",
        chat_history=shared_history,
    )
    response = await qwen_client.generate_response(
        request_id=request_id,
        messages=qwen_history,
        system_instruction=system_instruction,
        tools=qwen_tools,
        chat_history=shared_history,
    )
    master_agent_logger.info(
        "generate_qwen_response output=%s",
        response.model_dump_json(exclude_none=True),
    )

    reply = (response.message.content or "").strip()
    tool_calls = [
        {
            "name": tool_call.function.name,
            "arguments": tool_call.function.arguments,
        }
        for tool_call in (response.message.tool_calls or [])
    ]
    return reply, tool_calls
