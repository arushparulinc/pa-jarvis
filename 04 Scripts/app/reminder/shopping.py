"""Email a summary of all high-priority shopping items."""

import asyncio
import importlib
import os

import asyncpg

from ..call_storage import log_script_execution

gmail = importlib.import_module("app.002 Comms.gmail")


async def _connect_postgres() -> asyncpg.Connection:
    return await asyncpg.connect(
        host=os.getenv("PGSQL_HOSTNAME"),
        port=int(os.getenv("PGSQL_PORT", "5432")),
        user=os.getenv("PGSQL_USER"),
        password=os.getenv("PGSQL_PASSWORD"),
        database=os.getenv("PGSQL_DBNAME"),
    )


def _format_email(rows: list[asyncpg.Record]) -> str:
    if not rows:
        return "There are no high-priority items in the shopping list."

    lines = ["High-priority shopping items:", ""]
    for index, row in enumerate(rows, start=1):
        lines.append(f"{index}. {row['item_name']}")
        lines.append(f"   Status: {row['item_status']}")
        if row["item_description"]:
            lines.append(f"   Description: {row['item_description']}")
        lines.append("")
    return "\n".join(lines).rstrip()


@log_script_execution("reminder.shopping")
async def run() -> dict[str, str]:
    """Read all high-priority shopping items and email the formatted list."""
    connection = await _connect_postgres()
    try:
        rows = await connection.fetch(
            """
            SELECT item_name, item_description, item_status
            FROM toolsdata.shopping_list
            WHERE LOWER(item_priority) = 'high'
            ORDER BY created_at, item_id
            """
        )
    finally:
        await connection.close()

    return await asyncio.to_thread(
        gmail.gmail_send_email,
        "PA Jarvis: High-priority shopping items",
        _format_email(rows),
    )
