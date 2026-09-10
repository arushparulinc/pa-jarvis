import inspect

from . import (
    comm_tools,
    gdrive_tools,
    internet_tools,
    personal_tools,
    planner_tools,
    shopping_tools,
)


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
) -> object:
    """Find and execute a named function from an authorized tool module."""
    for module in tool_modules:
        tool_function = getattr(module, name, None)
        if callable(tool_function):
            result = tool_function(**(arguments or {}))
            if inspect.isawaitable(result):
                result = await result
            return result

    raise KeyError(f"Unknown tool: {name}")
