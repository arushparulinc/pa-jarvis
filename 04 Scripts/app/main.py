import os
import importlib
from contextlib import asynccontextmanager
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import asyncpg
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI


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
    connection = await asyncpg.connect(
        host=os.getenv("PGSQL_HOSTNAME"),
        port=int(os.getenv("PGSQL_PORT", "5432")),
        user=os.getenv("PGSQL_USER"),
        password=os.getenv("PGSQL_PASSWORD"),
        database=os.getenv("PGSQL_DBNAME"),
    )
    try:
        await media.register_jobs(scheduler, connection)
        await reminders.register_jobs(scheduler, connection)
        await misc.register_jobs(scheduler, connection)
    finally:
        await connection.close()
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
