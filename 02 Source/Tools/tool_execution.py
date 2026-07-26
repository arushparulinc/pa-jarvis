import inspect

from . import google_tools
from . import personal_tools


# List every module that is allowed to expose executable tools. Add future
# modules such as google_tools or cloud_tools here.
tool_modules = [
    personal_tools,
    google_tools,
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
