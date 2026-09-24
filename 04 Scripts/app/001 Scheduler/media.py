"""Schedules for individual media scripts."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncpg

from ..call_storage import log_scheduler_event
from ..media import pics, videos
from .schedule_store import load_schedules


SCRIPT_FUNCTIONS = {"pics": pics.run, "videos": videos.run}
SCRIPT_SCHEDULES: dict[int, dict[str, object]] = {}


async def register_jobs(scheduler: AsyncIOScheduler, connection: asyncpg.Connection) -> None:
    SCRIPT_SCHEDULES.clear()
    SCRIPT_SCHEDULES.update(await load_schedules(connection, ["media"], SCRIPT_FUNCTIONS))
    for schedule_id, schedule in SCRIPT_SCHEDULES.items():
        scheduler.add_job(
            schedule["func"],
            schedule["trigger"],
            **schedule["trigger_args"],
            id=f"media_{schedule['script_name']}_{schedule_id}",
            max_instances=1,
            coalesce=True,
        )
    await log_scheduler_event(
        event_name=f"Loaded {len(SCRIPT_SCHEDULES)} schedule(s)",
        event_type="SchedulesLoaded",
        scheduler_name="media",
    )
