import asyncio
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]
DEFAULT_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary").strip()
DEFAULT_TIME_ZONE = "America/Toronto"


class PlannerError(RuntimeError):
    """Raised when a planner operation cannot be completed."""


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
        raise PlannerError(f"Could not connect to PostgreSQL: {exc}") from exc


def _get_calendar_service():
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN", "").strip()

    missing_secrets = [
        name
        for name, value in (
            ("GOOGLE_CLIENT_ID", client_id),
            ("GOOGLE_CLIENT_SECRET", client_secret),
            ("GOOGLE_REFRESH_TOKEN", refresh_token),
        )
        if not value
    ]
    if missing_secrets:
        raise PlannerError(
            "Missing Google Calendar OAuth configuration: "
            + ", ".join(missing_secrets)
        )

    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=CALENDAR_SCOPES,
    )

    try:
        return build(
            "calendar",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )
    except (OSError, ValueError) as exc:
        raise PlannerError(
            f"Could not initialize the Google Calendar API: {exc}"
        ) from exc


async def add_calendar_event(
    event_name: str,
    start_time: str,
    end_time: str,
    event_description: str = "",
    time_zone: str = DEFAULT_TIME_ZONE,
    calendar_id: str = DEFAULT_CALENDAR_ID,
) -> dict[str, object]:
    """Create a Google Calendar event using RFC 3339 date-time values."""
    def create_event() -> dict[str, object]:
        try:
            return _get_calendar_service().events().insert(
                calendarId=calendar_id,
                body={
                    "summary": event_name,
                    "description": event_description,
                    "start": {"dateTime": start_time, "timeZone": time_zone},
                    "end": {"dateTime": end_time, "timeZone": time_zone},
                },
            ).execute()
        except HttpError as exc:
            raise PlannerError(f"Could not create calendar event: {exc}") from exc

    return await asyncio.to_thread(create_event)


async def read_calendar_event(
    event_id: str,
    calendar_id: str = DEFAULT_CALENDAR_ID,
) -> dict[str, object]:
    """Read one Google Calendar event by ID."""
    def read_event() -> dict[str, object]:
        try:
            return _get_calendar_service().events().get(
                calendarId=calendar_id,
                eventId=event_id,
            ).execute()
        except HttpError as exc:
            raise PlannerError(f"Could not read calendar event {event_id}: {exc}") from exc

    return await asyncio.to_thread(read_event)


async def list_calendar_events(
    time_min: str = "",
    time_max: str = "",
    max_results: int = 100,
    calendar_id: str = DEFAULT_CALENDAR_ID,
) -> list[dict[str, object]]:
    """List calendar events, optionally bounded by RFC 3339 timestamps."""
    def list_events() -> list[dict[str, object]]:
        query: dict[str, object] = {
            "calendarId": calendar_id,
            "singleEvents": True,
            "orderBy": "startTime",
            "maxResults": max_results,
        }
        if time_min:
            query["timeMin"] = time_min
        if time_max:
            query["timeMax"] = time_max
        try:
            return _get_calendar_service().events().list(**query).execute().get(
                "items", []
            )
        except HttpError as exc:
            raise PlannerError(f"Could not list calendar events: {exc}") from exc

    return await asyncio.to_thread(list_events)


async def delete_calendar_event(
    event_id: str,
    calendar_id: str = DEFAULT_CALENDAR_ID,
) -> dict[str, object]:
    """Delete one Google Calendar event by ID."""
    def delete_event() -> None:
        try:
            _get_calendar_service().events().delete(
                calendarId=calendar_id,
                eventId=event_id,
            ).execute()
        except HttpError as exc:
            raise PlannerError(f"Could not delete calendar event {event_id}: {exc}") from exc

    await asyncio.to_thread(delete_event)
    return {"deleted": True, "event_id": event_id}


def _task_record(row: asyncpg.Record) -> dict[str, object]:
    return {
        "task_id": row["task_id"],
        "task_name": row["task_name"],
        "task_description": row["task_description"],
        "created_at": row["created_at"].isoformat(),
    }


async def add_task(
    task_name: str,
    task_description: str = "",
) -> dict[str, object]:
    """Add a task to the PostgreSQL task list."""
    connection = await _connect_postgres()
    try:
        row = await connection.fetchrow(
            """
            INSERT INTO toolsdata.task_list (task_name, task_description)
            VALUES ($1, $2)
            RETURNING task_id, task_name, task_description, created_at
            """,
            task_name,
            task_description or None,
        )
        return _task_record(row)
    except asyncpg.UniqueViolationError as exc:
        raise PlannerError(f"Task already exists: {task_name}") from exc
    finally:
        await connection.close()


async def get_task(task_id: int) -> dict[str, object] | None:
    """Get one task by ID."""
    connection = await _connect_postgres()
    try:
        row = await connection.fetchrow(
            """
            SELECT task_id, task_name, task_description, created_at
            FROM toolsdata.task_list
            WHERE task_id = $1
            """,
            task_id,
        )
        return _task_record(row) if row else None
    finally:
        await connection.close()


async def list_tasks() -> list[dict[str, object]]:
    """List all tasks, newest first."""
    connection = await _connect_postgres()
    try:
        rows = await connection.fetch(
            """
            SELECT task_id, task_name, task_description, created_at
            FROM toolsdata.task_list
            ORDER BY created_at DESC, task_id DESC
            """
        )
        return [_task_record(row) for row in rows]
    finally:
        await connection.close()


async def delete_tasks(task_ids: list[int] | str) -> dict[str, object]:
    """Delete tasks by ID and return the IDs that were deleted."""
    if isinstance(task_ids, str):
        try:
            task_ids = [int(value.strip()) for value in task_ids.split(",")]
        except ValueError as exc:
            raise PlannerError("task_ids must contain comma-separated integers.") from exc

    connection = await _connect_postgres()
    try:
        rows = await connection.fetch(
            """
            DELETE FROM toolsdata.task_list
            WHERE task_id = ANY($1::bigint[])
            RETURNING task_id
            """,
            task_ids,
        )
        return {"deleted_task_ids": [row["task_id"] for row in rows]}
    finally:
        await connection.close()
