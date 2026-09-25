"""Email a summary of all high-priority shopping items."""

import asyncio
import csv
import importlib
from io import StringIO
import os

import asyncpg

from ..call_storage import log_script_execution

gmail = importlib.import_module("app.002 Comms.gmail")
gdrive = importlib.import_module("app.003 Storage.gdrive")

SHOPPING_GDRIVE_FOLDER_ID = "1wa_FmqNmZJ3Md3noXxcWA7GGc6Lzp5Ty"


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


def _format_csv(rows: list[asyncpg.Record]) -> str:
    columns = [
        "item_id",
        "item_name",
        "item_description",
        "item_priority",
        "item_status",
        "created_at",
        "closed_at",
    ]
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(columns)
    writer.writerows([row[column] for column in columns] for row in rows)
    return output.getvalue()


@log_script_execution("reminder.shopping")
async def run() -> dict[str, object]:
    """Read all high-priority shopping items and email the formatted list."""
    connection = await _connect_postgres()
    try:
        high_priority_rows = await connection.fetch(
            """
            SELECT item_name, item_description, item_status
            FROM toolsdata.shopping_list
            WHERE LOWER(item_priority) = 'high'
            ORDER BY created_at, item_id
            """
        )
        all_rows = await connection.fetch(
            """
            SELECT
                item_id,
                item_name,
                item_description,
                item_priority,
                item_status,
                created_at,
                closed_at
            FROM toolsdata.shopping_list
            ORDER BY created_at, item_id
            """
        )
    finally:
        await connection.close()

    email_result = await asyncio.to_thread(
        gmail.gmail_send_email,
        "PA Jarvis: High-priority shopping items",
        _format_email(high_priority_rows),
    )
    upload_result = await asyncio.to_thread(
        gdrive.upload_as_file_gdrive,
        SHOPPING_GDRIVE_FOLDER_ID,
        "csv",
        _format_csv(all_rows),
        "shopping_list.csv",
    )
    return {"email": email_result, "gdrive": upload_result}
