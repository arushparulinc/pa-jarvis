from google.genai import types


# Tell Gemini that it can request one random fact about Arush. The empty object
# schema means the function does not accept any arguments.
arush_random_facts = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="arush_random_facts",
            description="Provides a random fact about Arush.",
            parameters_json_schema={
                "type": "object",
                "properties": {},
            },
        )
    ]
)

# This is presented to the main LLM as a custom function. Its implementation
# makes a separate Gemini request that uses the real built-in Google Search.
google_search = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="google_search",
            description="Search Google to answer a current or factual request.",
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "request": {
                        "type": "string",
                        "description": (
                            "The complete search request, for example: "
                            "get the weather for Toronto"
                        ),
                    }
                },
                "required": ["request"],
            },
        )
    ]
)

def get_all_gemini_tools() -> list[types.Tool]:
    """Return every public Gemini Tool declared in this registry module."""
    return [
        value
        for name, value in globals().items()
        if not name.startswith("_") and isinstance(value, types.Tool)
    ]


def get_all_ollama_tools() -> list[dict[str, object]]:
    """Convert all function declarations to Ollama's tool schema."""
    ollama_tools: list[dict[str, object]] = []

    for tool in get_all_gemini_tools():
        for declaration in tool.function_declarations or []:
            parameters = declaration.parameters_json_schema or {
                "type": "object",
                "properties": {},
            }
            ollama_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": declaration.name,
                        "description": declaration.description or "",
                        "parameters": parameters,
                    },
                }
            )

    return ollama_tools
