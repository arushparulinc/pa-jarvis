import json
from datetime import datetime
from zoneinfo import ZoneInfo

from google.genai import types

from . import gemini_client, system_instructions, tools_registry
from .call_storage import log_event_pgsql, log_llm_call_pgsql


LLM_TIME_ZONE = ZoneInfo("America/Toronto")


def _append_current_date_time(system_instruction: str) -> str:
    """Append current local date and time to one LLM instruction."""
    current = datetime.now(LLM_TIME_ZONE)
    useful_info = (
        "USEFUL INFO\n"
        f"Date: {current:%Y-%m-%d}\n"
        f"Time: {current:%H:%M:%S}\n"
        f"Timezone: America/Toronto ({current.tzname()})\n"
        f"Day of the Week: {current:%A}"
    )
    return f"{system_instruction.rstrip()}\n\n{useful_info}"


async def route_chat_message_gemini(
    request_id: str,
    shared_history: list[dict[str, object]],
    calling_agent: str,
) -> tuple[str, list[dict[str, object]]]:
    """Make one Gemini request and return provider-neutral output."""
    # Convert the generic registry entries into Gemini tool definitions.
    gemini_tools = []
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

        gemini_tools.append(
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name=tool["name"],
                        description=tool["description"],
                        parameters_json_schema=parameter_schema,
                    )
                ]
            )
        )

    # Convert the shared provider-neutral history into Gemini content.
    gemini_history: list[types.Content] = []
    for item in shared_history:
        role = str(item["role"])

        if role == "tool":
            gemini_history.append(
                types.Content(
                    role="tool",
                    parts=[
                        types.Part.from_function_response(
                            name=str(item["tool_name"]),
                            response=item["tool_result"],
                        )
                    ],
                )
            )
            continue

        parts = []
        content = str(item.get("content", ""))
        if content:
            parts.append(types.Part.from_text(text=content))

        for tool_call in item.get("tool_calls", []):
            parts.append(
                types.Part.from_function_call(
                    name=str(tool_call["name"]),
                    args=tool_call.get("arguments", {}),
                )
            )

        gemini_history.append(
            types.Content(
                role="model" if role == "assistant" else "user",
                parts=parts,
            )
        )

    system_instruction = system_instructions.get_system_instructions(
        calling_agent
    )
    system_instruction = _append_current_date_time(system_instruction)
    chat_message = (
        str(shared_history[-1].get("content", ""))
        if shared_history
        else ""
    )
    await log_event_pgsql(
        request_id=request_id,
        chat_message=chat_message,
        service_name="llm",
        script_name="gemini_chat.py",
        event_type="call_gemini_client",
        chat_history=shared_history,
    )
    response = await gemini_client.generate_response(
        request_id=request_id,
        contents=gemini_history,
        system_instruction=system_instruction,
        tools=gemini_tools,
        chat_history=shared_history,
    )
    await log_llm_call_pgsql(
        request_id=request_id,
        calling_agent_name=calling_agent,
        message_sent=json.dumps(
            {
                "chat_history": shared_history,
                "system_instructions": system_instruction,
                "tools": [
                    tool.model_dump(mode="json", exclude_none=True)
                    for tool in gemini_tools
                ],
            },
            default=str,
        ),
        message_response=response.model_dump_json(exclude_none=True),
    )
    reply = response.text.strip() if response.text else ""
    tool_calls = [
        {
            "name": function_call.name or "",
            "arguments": function_call.args or {},
        }
        for function_call in (response.function_calls or [])
    ]
    return reply, tool_calls
