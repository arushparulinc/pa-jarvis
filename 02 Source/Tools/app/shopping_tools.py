import os
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
        "created_at": row["created_at"].isoformat(),
    }


async def add_item(
    item_name: str,
    item_description: str = "",
) -> dict[str, object]:
    """Add an item to the PostgreSQL shopping list."""
    connection = await _connect_postgres()
    try:
        row = await connection.fetchrow(
            """
            INSERT INTO toolsdata.shopping_list (item_name, item_description)
            VALUES ($1, $2)
            RETURNING item_id, item_name, item_description, created_at
            """,
            item_name,
            item_description or None,
        )
        return _item_record(row)
    except asyncpg.UniqueViolationError as exc:
        raise ShoppingError(f"Shopping item already exists: {item_name}") from exc
    finally:
        await connection.close()


async def get_item(item_id: int) -> dict[str, object] | None:
    """Get one shopping item by ID."""
    connection = await _connect_postgres()
    try:
        row = await connection.fetchrow(
            """
            SELECT item_id, item_name, item_description, created_at
            FROM toolsdata.shopping_list
            WHERE item_id = $1
            """,
            item_id,
        )
        return _item_record(row) if row else None
    finally:
        await connection.close()


async def list_items() -> list[dict[str, object]]:
    """List all shopping items, newest first."""
    connection = await _connect_postgres()
    try:
        rows = await connection.fetch(
            """
            SELECT item_id, item_name, item_description, created_at
            FROM toolsdata.shopping_list
            ORDER BY created_at DESC, item_id DESC
            """
        )
        return [_item_record(row) for row in rows]
    finally:
        await connection.close()


async def delete_items(item_ids: list[int] | str) -> dict[str, object]:
    """Delete shopping items by ID and return the IDs that were deleted."""
    if isinstance(item_ids, str):
        try:
            item_ids = [int(value.strip()) for value in item_ids.split(",")]
        except ValueError as exc:
            raise ShoppingError(
                "item_ids must contain comma-separated integers."
            ) from exc

    connection = await _connect_postgres()
    try:
        rows = await connection.fetch(
            """
            DELETE FROM toolsdata.shopping_list
            WHERE item_id = ANY($1::bigint[])
            RETURNING item_id
            """,
            item_ids,
        )
        return {"deleted_item_ids": [row["item_id"] for row in rows]}
    finally:
        await connection.close()
