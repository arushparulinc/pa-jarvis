"""Provider-neutral chat conversion for Groq."""

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from . import groq_client, system_instructions, tools_registry
from .call_storage import log_service_event_pgsql


LLM_TIME_ZONE = ZoneInfo("America/Toronto")


def _append_current_date_time(system_instruction: str) -> str:
    current = datetime.now(LLM_TIME_ZONE)
    useful_info = (
        "USEFUL INFO\n"
        f"Current Date: {current:%Y-%m-%d}\n"
        f"Current Time: {current:%H:%M:%S}\n"
        f"Timezone: America/Toronto ({current.tzname()})\n"
        f"Today is: {current:%A}"
    )
    return f"{system_instruction.rstrip()}\n\n{useful_info}"


def _groq_tools(calling_agent: str) -> list[dict[str, object]]:
    tools: list[dict[str, object]] = []
    for tool in tools_registry.get_all_tools(calling_agent):
        parameters = tool["parameters"]
        schema: dict[str, object] = {
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
            schema["required"] = required
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": schema,
                },
            }
        )
    return tools


def _groq_history(
    shared_history: list[dict[str, object]],
) -> list[dict[str, object]]:
    messages: list[dict[str, object]] = []
    pending_tool_calls: list[tuple[str, str]] = []
    for message_index, item in enumerate(shared_history):
        role = str(item["role"])
        if role == "tool":
            tool_name = str(item["tool_name"])
            matching_index = next(
                (
                    index
                    for index, (name, _) in enumerate(pending_tool_calls)
                    if name == tool_name
                ),
                0,
            )
            if pending_tool_calls:
                _, tool_call_id = pending_tool_calls.pop(matching_index)
            else:
                tool_call_id = f"call_{message_index}_0"
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": json.dumps(item["tool_result"], default=str),
                }
            )
            continue

        converted: dict[str, object] = {
            "role": role,
            "content": str(item.get("content", "")),
        }
        if role == "assistant" and item.get("tool_calls"):
            converted_calls = []
            for call_index, tool_call in enumerate(item["tool_calls"]):
                tool_call_id = f"call_{message_index}_{call_index}"
                tool_name = str(tool_call["name"])
                pending_tool_calls.append((tool_name, tool_call_id))
                converted_calls.append(
                    {
                        "id": tool_call_id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(
                                tool_call.get("arguments", {}),
                                default=str,
                            ),
                        },
                    }
                )
            converted["tool_calls"] = converted_calls
        messages.append(converted)
    return messages


def _parse_response(
    response: dict[str, object],
) -> tuple[str, list[dict[str, object]]]:
    try:
        message = response["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise groq_client.GroqError(
            "Groq response does not contain an assistant message."
        ) from exc

    reply = str(message.get("content") or "").strip()
    tool_calls: list[dict[str, object]] = []
    for tool_call in message.get("tool_calls") or []:
        function = tool_call.get("function") or {}
        raw_arguments = function.get("arguments") or "{}"
        try:
            arguments = (
                raw_arguments
                if isinstance(raw_arguments, dict)
                else json.loads(raw_arguments)
            )
        except (TypeError, json.JSONDecodeError) as exc:
            raise groq_client.GroqError(
                f"Groq returned invalid arguments for tool {function.get('name')}."
            ) from exc
        if not isinstance(arguments, dict):
            raise groq_client.GroqError("Groq tool arguments must be an object.")
        tool_calls.append(
            {"name": str(function.get("name") or ""), "arguments": arguments}
        )
    return reply, tool_calls


async def route_chat_message_groq(
    request_id: str,
    shared_history: list[dict[str, object]],
    calling_agent: str,
) -> tuple[str, list[dict[str, object]]]:
    """Make one Groq request and return provider-neutral output."""
    tools = _groq_tools(calling_agent)
    system_instruction = _append_current_date_time(
        system_instructions.get_system_instructions(calling_agent)
    )
    chat_message = (
        str(shared_history[-1].get("content", "")) if shared_history else ""
    )
    await log_service_event_pgsql(
        request_id=request_id,
        chat_message=chat_message,
        service_name="llm",
        script_name="groq_chat.py",
        event_type="call_groq_client",
        chat_history=shared_history,
    )
    response = await groq_client.generate_response(
        request_id=request_id,
        calling_agent=calling_agent,
        messages=_groq_history(shared_history),
        system_instruction=system_instruction,
        tools=tools,
        chat_history=shared_history,
    )
    return _parse_response(response)
