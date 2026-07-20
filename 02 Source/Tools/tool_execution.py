from . import personal_tools


def execute_tool(name: str, arguments: dict[str, object] | None = None) -> object:
    """Execute the personal-tools function whose name Gemini requested."""
    tool_function = getattr(personal_tools, name, None)
    if not callable(tool_function):
        raise KeyError(f"Unknown tool: {name}")

    return tool_function(**(arguments or {}))
