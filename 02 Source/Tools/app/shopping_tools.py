import os
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

import asyncpg
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


class ShoppingError(RuntimeError):
    """Raised when a shopping-list operation cannot be completed."""


async def _connect_postgres() -> asyncpg.Connection:
    try:
        return await asyncpg.connect(
            host=os.getenv("PGSQL_HOSTNAME"),
            port=int(os.getenv("PGSQL_PORT", "5432")),
            user=os.getenv("PGSQL_USER"),
            password=os.getenv("PGSQL_PASSWORD"),
            database=os.getenv("PGSQL_DBNAME"),
        )
    except Exception as exc:
        raise ShoppingError(f"Could not connect to PostgreSQL: {exc}") from exc


def _item_record(row: asyncpg.Record) -> dict[str, object]:
    return {
        "item_id": row["item_id"],
        "item_name": row["item_name"],
        "item_description": row["item_description"],
        "item_priority": row["item_priority"],
        "item_status": row["item_status"],
        "created_at": row["created_at"].isoformat(),
        "closed_at": row["closed_at"].isoformat() if row["closed_at"] else None,
    }


def _closest_item(rows: list[asyncpg.Record], item_name: str, *, mutation: bool = False) -> asyncpg.Record | None:
    search_name = item_name.strip().casefold()
    if not search_name:
        raise ShoppingError("item_name must not be empty.")

    ranked = sorted(
        (
            (SequenceMatcher(None, search_name, row["item_name"].strip().casefold()).ratio(), row)
            for row in rows
        ),
        key=lambda match: match[0],
        reverse=True,
    )
    minimum_score = 0.8 if mutation else 0.6
    if not ranked or ranked[0][0] < minimum_score:
        return None
    if mutation and len(ranked) > 1 and ranked[0][0] - ranked[1][0] < 0.1:
        raise ShoppingError("Item name is ambiguous; please provide a more specific name.")
    return ranked[0][1]


async def add_item(
    item_name: str,
    item_description: str = "",
    item_priority: str = "",
) -> dict[str, object]:
    """Add an item to the PostgreSQL shopping list."""
    connection = await _connect_postgres()
    try:
        row = await connection.fetchrow(
            """
            INSERT INTO toolsdata.shopping_list (
                item_name,
                item_description,
                item_priority
            )
            VALUES ($1, $2, $3)
            RETURNING
                item_id,
                item_name,
                item_description,
                item_priority,
                item_status,
                created_at,
                closed_at
            """,
            item_name,
            item_description or None,
            item_priority or None,
        )
        return _item_record(row)
    except asyncpg.UniqueViolationError as exc:
        raise ShoppingError(f"Shopping item already exists: {item_name}") from exc
    finally:
        await connection.close()


async def get_item(item_name: str) -> dict[str, object] | None:
    """Get the closest matching shopping item by name."""
    connection = await _connect_postgres()
    try:
        rows = await connection.fetch(
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
            """
        )
        match = _closest_item(rows, item_name)
        return _item_record(match) if match else None
    finally:
        await connection.close()


async def update_item(
    item_name: str,
    item_priority: str | None = None,
    item_status: str | None = None,
    closed_at: str | None = None,
) -> dict[str, object] | None:
    """Update the closest unambiguous shopping item by name."""
    if item_priority is None and item_status is None and closed_at is None:
        raise ShoppingError("Provide item_priority, item_status, or closed_at to update.")

    closed_at_value = None
    if closed_at is not None:
        try:
            closed_at_value = datetime.fromisoformat(closed_at)
        except ValueError as exc:
            raise ShoppingError("closed_at must be an ISO 8601 date-time.") from exc
        if closed_at_value.tzinfo is not None:
            closed_at_value = closed_at_value.astimezone(timezone.utc).replace(tzinfo=None)

    connection = await _connect_postgres()
    try:
        async with connection.transaction():
            rows = await connection.fetch(
                "SELECT item_id, item_name FROM toolsdata.shopping_list FOR UPDATE"
            )
            match = _closest_item(rows, item_name, mutation=True)
            if match is None:
                return None
            row = await connection.fetchrow(
                """
                UPDATE toolsdata.shopping_list
                SET item_priority = COALESCE($2, item_priority),
                    item_status = COALESCE($3, item_status),
                    closed_at = COALESCE($4, closed_at)
                WHERE item_id = $1
                RETURNING item_id, item_name, item_description, item_priority,
                          item_status, created_at, closed_at
                """,
                match["item_id"], item_priority, item_status, closed_at_value,
            )
            return _item_record(row)
    finally:
        await connection.close()


async def list_items() -> list[dict[str, object]]:
    """List all shopping items, newest first."""
    connection = await _connect_postgres()
    try:
        rows = await connection.fetch(
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
            ORDER BY created_at DESC, item_id DESC
            """
        )
        return [_item_record(row) for row in rows]
    finally:
        await connection.close()


async def delete_item(item_name: str) -> dict[str, object]:
    """Delete the closest unambiguous shopping item by name."""
    connection = await _connect_postgres()
    try:
        async with connection.transaction():
            rows = await connection.fetch(
                "SELECT item_id, item_name FROM toolsdata.shopping_list FOR UPDATE"
            )
            match = _closest_item(rows, item_name, mutation=True)
            if match is None:
                return {"deleted": False}
            row = await connection.fetchrow(
                """
                DELETE FROM toolsdata.shopping_list
                WHERE item_id = $1
                RETURNING item_id, item_name
                """,
                match["item_id"],
            )
            return {"deleted": True, "item_id": row["item_id"], "item_name": row["item_name"]}
    finally:
        await connection.close()
