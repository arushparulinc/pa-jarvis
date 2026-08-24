import asyncio
import json
import os
import re
from functools import lru_cache
from pathlib import Path

import asyncpg
from dotenv import load_dotenv


class ToolsRegistryError(RuntimeError):
    """Raised when tool definitions cannot be loaded from PostgreSQL."""


TOOLS_REGISTRY_FILE = Path(__file__).resolve().parents[1] / "tools_registry.txt"
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

SCHEMA_TYPE_MAP = {
    "array": "array",
    "bigint": "integer",
    "bool": "boolean",
    "boolean": "boolean",
    "character varying": "string",
    "decimal": "number",
    "dict": "object",
    "double": "number",
    "float": "number",
    "int": "integer",
    "integer": "integer",
    "json": "object",
    "jsonb": "object",
    "list": "array",
    "number": "number",
    "numeric": "number",
    "object": "object",
    "smallint": "integer",
    "str": "string",
    "string": "string",
    "text": "string",
    "timestamp": "string",
    "timestamp without time zone": "string",
    "timestamp with time zone": "string",
    "timestamptz": "string",
    "timestampz": "string",
    "varchar": "string",
}


def _normalize_identifier(value: object) -> str:
    """Convert a database label into an LLM function-safe identifier."""
    identifier = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value).strip())
    return identifier.strip("_").lower()


def _normalize_schema_type(value: object) -> str:
    """Convert a database parameter type into a JSON Schema type."""
    database_type = str(value).strip().casefold()
    schema_type = SCHEMA_TYPE_MAP.get(database_type)
    if schema_type is None:
        raise ToolsRegistryError(
            f"Unsupported tool parameter type: {value!r}."
        )
    return schema_type


async def refresh_tools_registry() -> None:
    """Load tool definitions from PostgreSQL and write the local cache."""
    try:
        connection = await asyncpg.connect(
            host=os.getenv("PGSQL_HOSTNAME"),
            port=int(os.getenv("PGSQL_PORT", "5432")),
            user=os.getenv("PGSQL_USER"),
            password=os.getenv("PGSQL_PASSWORD"),
            database=os.getenv("PGSQL_DBNAME"),
        )
    except Exception as exc:
        raise ToolsRegistryError(
            f"Could not connect to PostgreSQL for tool definitions: {exc}"
        ) from exc

    try:
        rows = await connection.fetch(
            """
            SELECT
                tr.agent_id,
                a.agent_name,
                a.agent_description,
                tr.tool_id,
                tr.tool_name,
                tr.tool_description,
                tp.param_name,
                tp.param_type,
                tp.param_description,
                tp.is_required
            FROM config.tools_registry AS tr
            INNER JOIN config.agents AS a
                ON a.agent_id = tr.agent_id
            LEFT JOIN config.tools_parameters AS tp
                ON tp.tool_id = tr.tool_id
            ORDER BY tr.agent_id, tr.tool_id, tp.param_name NULLS LAST
            """
        )
    except asyncpg.UndefinedTableError as exc:
        raise ToolsRegistryError(
            "PostgreSQL tables 'config.tools_registry' and "
            "'config.tools_parameters' "
            "must exist."
        ) from exc
    except asyncpg.UndefinedColumnError as exc:
        raise ToolsRegistryError(
            "PostgreSQL tool-registry tables do not match the required "
            "column structure."
        ) from exc
    except Exception as exc:
        raise ToolsRegistryError(
            f"Could not load tool definitions: {exc}"
        ) from exc
    finally:
        await connection.close()

    tools_by_id: dict[object, dict[str, object]] = {}
    for row in rows:
        tool_id = row["tool_id"]
        tool = tools_by_id.setdefault(
            tool_id,
            {
                "agent_id": str(row["agent_id"]),
                "agent_name": str(row["agent_name"]).strip(),
                "name": _normalize_identifier(row["tool_name"]),
                "description": str(row["tool_description"]).strip(),
                "parameters": [],
            },
        )

        if row["param_name"] is not None:
            parameters = tool["parameters"]
            if not isinstance(parameters, list):
                raise ToolsRegistryError("Invalid reconstructed parameter list.")
            parameters.append(
                {
                    "name": _normalize_identifier(row["param_name"]),
                    "type": _normalize_schema_type(row["param_type"]),
                    "description": str(row["param_description"]).strip(),
                    "required": bool(row["is_required"]),
                }
            )

    tools = list(tools_by_id.values())
    if not tools:
        raise ToolsRegistryError(
            "No tools were found in 'config.tools_registry'."
        )

    TOOLS_REGISTRY_FILE.write_text(
        json.dumps(tools, indent=2),
        encoding="utf-8",
    )


@lru_cache(maxsize=1)
def _get_cached_tools() -> list[dict[str, object]]:
    """Read the startup-generated tool registry cache once."""
    try:
        tools = json.loads(TOOLS_REGISTRY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolsRegistryError(
            f"Could not read '{TOOLS_REGISTRY_FILE}': {exc}"
        ) from exc

    if not isinstance(tools, list) or not tools:
        raise ToolsRegistryError(
            f"Tool-registry cache '{TOOLS_REGISTRY_FILE}' is empty or invalid."
        )
    return tools


def get_all_tools(calling_agent: str) -> list[dict[str, object]]:
    """Return cached tool definitions belonging to one calling agent."""
    requested_name = calling_agent.strip().casefold()
    tools = [
        tool
        for tool in _get_cached_tools()
        if str(tool.get("agent_name", "")).strip().casefold() == requested_name
    ]
    return tools


if __name__ == "__main__":
    asyncio.run(refresh_tools_registry())
