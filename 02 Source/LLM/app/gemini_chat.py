from google.genai import types

from . import gemini_client, system_instructions, tools_registry
from .call_storage import log_event_pgsql


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
    reply = response.text.strip() if response.text else ""
    tool_calls = [
        {
            "name": function_call.name or "",
            "arguments": function_call.args or {},
        }
        for function_call in (response.function_calls or [])
    ]
    return reply, tool_calls
