"""Load and validate script schedules through the Storage service."""

from collections.abc import Callable, Sequence

from ..call_storage import get_script_schedules


async def load_schedules(
    sched_types: Sequence[str],
    scripts: dict[str, Callable[[], object]],
) -> dict[int, dict[str, object]]:
    rows = await get_script_schedules(list(sched_types))

    schedules: dict[int, dict[str, object]] = {}
    for row in rows:
        schedule_id = int(row["sched_id"])
        name = row["sched_name"].strip().casefold()
        if name not in scripts:
            raise ValueError(f"Unknown script schedule: {sched_types[0]}/{name}")

        day_of_week = row["sched_day_of_week"].strip()
        hour = row["sched_hour"]
        minute = row["sched_minute"]
        if not day_of_week or hour is None or minute is None:
            raise ValueError(f"Incomplete script schedule: {sched_types[0]}/{name}")
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            raise ValueError(f"Invalid time for script schedule: {sched_types[0]}/{name}")

        schedules[schedule_id] = {
            "script_name": name,
            "func": scripts[name],
            "trigger": "cron",
            "trigger_args": {
                "day_of_week": day_of_week,
                "hour": int(hour),
                "minute": int(minute),
            },
        }
    return schedules
