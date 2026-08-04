# Keep tool declarations with the LLM service. The Tools service owns only the
# executable implementations and receives tool names over HTTP.
TOOLS = [
    {
        "name": "arush_random_facts",
        "description": "Provides a random fact about Arush.",
        "parameters": [],
    },
    {
        "name": "google_search",
        "description": "Search Google to answer a current or factual request.",
        "parameters": [
            {
                "name": "request",
                "type": "string",
                "description": "The complete request to search for.",
                "required": True,
            }
        ],
    },
    {
        "name": "gdrive_read",
        "description": "Read a specific file from Google Drive.",
        "parameters": [
            {
                "name": "file_id",
                "type": "string",
                "description": "The Google Drive ID of the file to read.",
                "required": True,
            }
        ],
    },
    {
        "name": "gdrive_write",
        "description": (
            "Upload a local file into a specific Google Drive folder."
        ),
        "parameters": [
            {
                "name": "local_file_path",
                "type": "string",
                "description": "The local path of the file to upload.",
                "required": True,
            },
            {
                "name": "folder_id",
                "type": "string",
                "description": "The destination Google Drive folder ID.",
                "required": True,
            },
            {
                "name": "file_name",
                "type": "string",
                "description": (
                    "Optional destination filename. Defaults to the local name."
                ),
                "required": False,
            },
        ],
    },
    {
        "name": "gdrive_delete",
        "description": "Permanently delete a specific Google Drive file.",
        "parameters": [
            {
                "name": "file_id",
                "type": "string",
                "description": "The Google Drive ID of the file to delete.",
                "required": True,
            }
        ],
    },
    {
        "name": "gdrive_list",
        "description": "List files in a specific Google Drive folder.",
        "parameters": [
            {
                "name": "folder_id",
                "type": "string",
                "description": "The Google Drive folder ID to list.",
                "required": True,
            }
        ],
    },
]


def get_all_tools() -> list[dict[str, object]]:
    """Return names, descriptions, and parameters for all available tools."""
    return [
        {
            **tool,
            "parameters": [
                parameter.copy()
                for parameter in tool["parameters"]
            ],
        }
        for tool in TOOLS
    ]
