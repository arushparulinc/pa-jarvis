"""Load and validate script schedules from PostgreSQL."""

from collections.abc import Callable, Sequence

import asyncpg


async def load_schedules(
    connection: asyncpg.Connection,
    sched_types: Sequence[str],
    scripts: dict[str, Callable[[], object]],
) -> dict[str, dict[str, object]]:
    rows = await connection.fetch(
        """
        SELECT sched_name, sched_day_of_week, sched_hour, sched_minute
        FROM config.script_schedules
        WHERE sched_type = ANY($1::varchar[])
        ORDER BY sched_id
        """,
        list(sched_types),
    )

    schedules: dict[str, dict[str, object]] = {}
    for row in rows:
        name = row["sched_name"].strip().casefold()
        if name not in scripts:
            raise ValueError(f"Unknown script schedule: {sched_types[0]}/{name}")
        if name in schedules:
            raise ValueError(f"Duplicate script schedule: {sched_types[0]}/{name}")

        day_of_week = row["sched_day_of_week"].strip()
        hour = row["sched_hour"]
        minute = row["sched_minute"]
        if not day_of_week or hour is None or minute is None:
            raise ValueError(f"Incomplete script schedule: {sched_types[0]}/{name}")
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            raise ValueError(f"Invalid time for script schedule: {sched_types[0]}/{name}")

        schedules[name] = {
            "func": scripts[name],
            "trigger": "cron",
            "trigger_args": {
                "day_of_week": day_of_week,
                "hour": int(hour),
                "minute": int(minute),
            },
        }
    return schedules
