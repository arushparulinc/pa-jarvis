"""Email a summary of all high-priority tasks."""

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
        return "There are no high-priority tasks in the task list."

    lines = ["High-priority tasks:", ""]
    for index, row in enumerate(rows, start=1):
        lines.append(f"{index}. {row['task_name']}")
        lines.append(f"   Status: {row['task_status']}")
        if row["task_description"]:
            lines.append(f"   Description: {row['task_description']}")
        lines.append("")
    return "\n".join(lines).rstrip()


@log_script_execution("reminder.tasks")
async def run() -> dict[str, str]:
    """Read all high-priority tasks and email the formatted list."""
    connection = await _connect_postgres()
    try:
        rows = await connection.fetch(
            """
            SELECT task_name, task_description, task_status
            FROM toolsdata.task_list
            WHERE LOWER(task_priority) = 'high'
            ORDER BY created_at, task_id
            """
        )
    finally:
        await connection.close()

    return await asyncio.to_thread(
        gmail.gmail_send_email,
        "PA Jarvis: High-priority tasks",
        _format_email(rows),
    )
