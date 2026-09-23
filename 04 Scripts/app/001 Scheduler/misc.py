"""Schedules for individual miscellaneous scripts."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncpg

from ..misc import quotes
from .schedule_store import load_schedules


SCRIPT_FUNCTIONS = {"quotes": quotes.run}
SCRIPT_SCHEDULES: dict[str, dict[str, object]] = {}


async def register_jobs(scheduler: AsyncIOScheduler, connection: asyncpg.Connection) -> None:
    SCRIPT_SCHEDULES.clear()
    SCRIPT_SCHEDULES.update(await load_schedules(connection, ["misc"], SCRIPT_FUNCTIONS))
    for script_name, schedule in SCRIPT_SCHEDULES.items():
        scheduler.add_job(
            schedule["func"],
            schedule["trigger"],
            **schedule["trigger_args"],
            id=f"misc_{script_name}",
            max_instances=1,
            coalesce=True,
        )
