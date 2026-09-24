import os
from typing import Any

import asyncpg


async def create_pool() -> asyncpg.Pool:
    """Create the shared PostgreSQL connection pool used by the dashboard."""
    return await asyncpg.create_pool(
        host=os.getenv("PGSQL_HOSTNAME"),
        port=int(os.getenv("PGSQL_PORT", "5432")),
        user=os.getenv("PGSQL_USER"),
        password=os.getenv("PGSQL_PASSWORD"),
        database=os.getenv("PGSQL_DBNAME"),
        min_size=1,
        max_size=int(os.getenv("PGSQL_POOL_MAX_SIZE", "5")),
        command_timeout=float(os.getenv("PGSQL_COMMAND_TIMEOUT_SECONDS", "10")),
    )


async def get_high_priority_items(
    pool: asyncpg.Pool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return high-priority tasks and shopping items for the dashboard."""
    async with pool.acquire() as connection:
        task_rows = await connection.fetch(
            """
            SELECT
                task_id,
                task_name,
                task_description,
                task_priority,
                task_status,
                created_at,
                closed_at
            FROM toolsdata.task_list
            WHERE LOWER(TRIM(task_priority)) = 'high'
            ORDER BY
                CASE WHEN LOWER(TRIM(task_status)) = 'open' THEN 0 ELSE 1 END,
                created_at DESC
            """
        )
        shopping_rows = await connection.fetch(
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
            WHERE LOWER(TRIM(item_priority)) = 'high'
            ORDER BY
                CASE WHEN LOWER(TRIM(item_status)) = 'open' THEN 0 ELSE 1 END,
                created_at DESC
            """
        )

    return [dict(row) for row in task_rows], [dict(row) for row in shopping_rows]
