import importlib
import os
from contextlib import asynccontextmanager
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from .reminder import events


media = importlib.import_module("app.001 Scheduler.media")
misc = importlib.import_module("app.001 Scheduler.misc")
reminders = importlib.import_module("app.001 Scheduler.reminders")


@asynccontextmanager
async def lifespan(app: FastAPI):
    timezone_name = os.getenv("SCRIPTS_TIME_ZONE", "America/Toronto")
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise RuntimeError(f"Unknown SCRIPTS_TIME_ZONE: {timezone_name}") from exc

    scheduler = AsyncIOScheduler(timezone=timezone)
    await media.register_jobs(scheduler)
    await reminders.register_jobs(scheduler)
    await misc.register_jobs(scheduler)
    scheduler.start()
    app.state.scheduler = scheduler
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="PA Jarvis Scripts Service", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "scripts-service"}


@app.post("/reminders/events/sync")
async def sync_calendar_events() -> dict[str, object]:
    """Refresh the PostgreSQL cache from the primary Google Calendar."""
    return await events.run()
