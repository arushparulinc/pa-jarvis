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

def get_all_tools() -> list[types.Tool]:
    """Return every public Gemini Tool declared in this registry module."""
    return [
        value
        for name, value in globals().items()
        if not name.startswith("_") and isinstance(value, types.Tool)
    ]
