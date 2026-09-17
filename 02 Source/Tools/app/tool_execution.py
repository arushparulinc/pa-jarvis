import inspect
import json

from . import (
    comm_tools,
    gdrive_tools,
    internet_tools,
    personal_tools,
    planner_tools,
    shopping_tools,
)
from .call_storage import log_tool_call_pgsql


# List every module that is allowed to expose executable tools. Add future
# modules here so their public functions can be executed by name.
tool_modules = [
    personal_tools,
    gdrive_tools,
    internet_tools,
    comm_tools,
    planner_tools,
    shopping_tools,
]


async def execute_tool(
    name: str,
    arguments: dict[str, object] | None = None,
    *,
    request_id: str,
    calling_agent_name: str,
) -> object:
    """Find and execute a named function from an authorized tool module."""
    tool_arguments = arguments or {}

    try:
        for module in tool_modules:
            tool_function = getattr(module, name, None)
            if callable(tool_function):
                result = tool_function(**tool_arguments)
                if inspect.isawaitable(result):
                    result = await result
                break
        else:
            raise KeyError(f"Unknown tool: {name}")
    except Exception as exc:
        await log_tool_call_pgsql(
            request_id=request_id,
            calling_agent_name=calling_agent_name,
            tool_name=name,
            tool_arguments=json.dumps(tool_arguments, default=str),
            tool_output=json.dumps(
                {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                default=str,
            ),
        )
        raise

    await log_tool_call_pgsql(
        request_id=request_id,
        calling_agent_name=calling_agent_name,
        tool_name=name,
        tool_arguments=json.dumps(tool_arguments, default=str),
        tool_output=json.dumps(result, default=str),
    )
    return result
