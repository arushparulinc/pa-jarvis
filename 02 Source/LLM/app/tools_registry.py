import asyncio
import json
import os
from functools import lru_cache
from pathlib import Path

import asyncpg


class ToolsRegistryError(RuntimeError):
    """Raised when tool definitions cannot be loaded from PostgreSQL."""


TOOLS_REGISTRY_FILE = Path(__file__).resolve().parents[1] / "tools_registry.txt"


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
                tr.tool_id,
                tr.tool_name,
                tr.tool_description,
                tp.param_name,
                tp.param_type,
                tp.param_description,
                tp.is_required
            FROM tools_registry AS tr
            LEFT JOIN tools_parameters AS tp
                ON tp.tool_id = tr.tool_id
            ORDER BY tr.tool_id, tp.param_name NULLS LAST
            """
        )
    except asyncpg.UndefinedTableError as exc:
        raise ToolsRegistryError(
            "PostgreSQL tables 'tools_registry' and 'tools_parameters' "
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
                "name": str(row["tool_name"]).strip(),
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
                    "name": str(row["param_name"]).strip(),
                    "type": str(row["param_type"]).strip(),
                    "description": str(row["param_description"]).strip(),
                    "required": bool(row["is_required"]),
                }
            )

    tools = list(tools_by_id.values())
    if not tools:
        raise ToolsRegistryError("No tools were found in 'tools_registry'.")

    TOOLS_REGISTRY_FILE.write_text(
        json.dumps(tools, indent=2),
        encoding="utf-8",
    )


@lru_cache(maxsize=1)
def get_all_tools() -> list[dict[str, object]]:
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


if __name__ == "__main__":
    asyncio.run(refresh_tools_registry())
