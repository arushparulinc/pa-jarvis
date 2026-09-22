import asyncio
import os
from difflib import SequenceMatcher
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
    event_start_time: str,
    event_duration_hrs: int | float = 1,
    event_description: str = "",
    event_priority: str = "",
    time_zone: str = DEFAULT_TIME_ZONE,
    calendar_id: str = DEFAULT_CALENDAR_ID,
) -> dict[str, object]:
    """Create an event, deriving its end from the start and duration."""
    try:
        calendar_time_zone = ZoneInfo(time_zone)
    except ZoneInfoNotFoundError as exc:
        raise PlannerError(f"Unknown calendar time zone: {time_zone}") from exc

    try:
        normalized_start = event_start_time.strip().replace("Z", "+00:00")
        if ":" in normalized_start and "T" not in normalized_start:
            parsed_time = time.fromisoformat(normalized_start)
            start = datetime.combine(
                datetime.now(calendar_time_zone).date(),
                parsed_time,
                tzinfo=calendar_time_zone,
            )
        else:
            start = datetime.fromisoformat(normalized_start)
            if start.tzinfo is None:
                start = start.replace(tzinfo=calendar_time_zone)

        duration = float(event_duration_hrs)
        if duration <= 0:
            raise ValueError("duration must be greater than zero")
    except (TypeError, ValueError) as exc:
        raise PlannerError(
            "event_start_time must be an ISO 8601 date-time or time, and "
            "event_duration_hrs must be greater than zero."
        ) from exc

    end = start + timedelta(hours=duration)
    event_body: dict[str, object] = {
        "summary": event_name,
        "description": event_description,
        "start": {"dateTime": start.isoformat(), "timeZone": time_zone},
        "end": {"dateTime": end.isoformat(), "timeZone": time_zone},
    }
    if event_priority.strip():
        event_body["extendedProperties"] = {
            "private": {"priority": event_priority.strip()}
        }

    def create_event() -> dict[str, object]:
        try:
            return _get_calendar_service().events().insert(
                calendarId=calendar_id,
                body=event_body,
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
        "task_priority": row["task_priority"],
        "task_description": row["task_description"],
        "task_status": row["task_status"],
        "created_at": row["created_at"].isoformat(),
        "closed_at": row["closed_at"].isoformat() if row["closed_at"] else None,
    }


def _closest_task(rows: list[asyncpg.Record], task_name: str, *, mutation: bool = False) -> asyncpg.Record | None:
    search_name = task_name.strip().casefold()
    if not search_name:
        raise PlannerError("task_name must not be empty.")

    ranked = sorted(
        (
            (SequenceMatcher(None, search_name, row["task_name"].strip().casefold()).ratio(), row)
            for row in rows
        ),
        key=lambda match: match[0],
        reverse=True,
    )
    minimum_score = 0.8 if mutation else 0.6
    if not ranked or ranked[0][0] < minimum_score:
        return None
    if mutation and len(ranked) > 1 and ranked[0][0] - ranked[1][0] < 0.1:
        raise PlannerError("Task name is ambiguous; please provide a more specific name.")
    return ranked[0][1]


async def add_task(
    task_name: str,
    task_description: str = "",
    task_priority: str = "Not-Defined",
    task_status: str = "Open",
) -> dict[str, object]:
    """Add a task to the PostgreSQL task list."""
    connection = await _connect_postgres()
    try:
        row = await connection.fetchrow(
            """
            INSERT INTO toolsdata.task_list (task_name, task_description, task_priority, task_status)
            VALUES ($1, $2, $3, $4)
            RETURNING task_id, task_name, task_priority, task_description, task_status, created_at, closed_at
            """,
            task_name,
            task_description or None,
            task_priority or "Not-Defined",
            task_status or "Open",
        )
        return _task_record(row)
    except asyncpg.UniqueViolationError as exc:
        raise PlannerError(f"Task already exists: {task_name}") from exc
    finally:
        await connection.close()


async def get_task(task_name: str) -> dict[str, object] | None:
    """Get the closest matching task by name, or None if none is close enough."""
    connection = await _connect_postgres()
    try:
        rows = await connection.fetch(
            """
            SELECT task_id, task_name, task_priority, task_description, task_status, created_at, closed_at
            FROM toolsdata.task_list
            """
        )
        match = _closest_task(rows, task_name)
        return _task_record(match) if match else None
    finally:
        await connection.close()


async def update_task(
    task_name: str,
    task_status: str | None = None,
    task_priority: str | None = None,
    closed_at: str | None = None,
) -> dict[str, object] | None:
    """Update the closest unambiguous task by name."""
    if task_status is None and task_priority is None and closed_at is None:
        raise PlannerError("Provide task_status, task_priority, or closed_at to update.")

    closed_at_value = None
    if closed_at is not None:
        try:
            closed_at_value = datetime.fromisoformat(closed_at)
        except ValueError as exc:
            raise PlannerError("closed_at must be an ISO 8601 date-time.") from exc
        if closed_at_value.tzinfo is not None:
            closed_at_value = closed_at_value.astimezone(timezone.utc).replace(tzinfo=None)

    connection = await _connect_postgres()
    try:
        async with connection.transaction():
            rows = await connection.fetch(
                "SELECT task_id, task_name FROM toolsdata.task_list FOR UPDATE"
            )
            match = _closest_task(rows, task_name, mutation=True)
            if match is None:
                return None
            row = await connection.fetchrow(
                """
                UPDATE toolsdata.task_list
                SET task_status = COALESCE($2, task_status),
                    task_priority = COALESCE($3, task_priority),
                    closed_at = COALESCE($4, closed_at)
                WHERE task_id = $1
                RETURNING task_id, task_name, task_priority, task_description,
                          task_status, created_at, closed_at
                """,
                match["task_id"], task_status, task_priority, closed_at_value,
            )
            return _task_record(row)
    finally:
        await connection.close()


async def list_tasks() -> list[dict[str, object]]:
    """List all tasks, newest first."""
    connection = await _connect_postgres()
    try:
        rows = await connection.fetch(
            """
            SELECT task_id, task_name, task_priority, task_description, task_status, created_at, closed_at
            FROM toolsdata.task_list
            ORDER BY created_at DESC, task_id DESC
            """
        )
        return [_task_record(row) for row in rows]
    finally:
        await connection.close()


async def delete_task(task_name: str) -> dict[str, object]:
    """Delete the closest unambiguous task by name."""
    connection = await _connect_postgres()
    try:
        async with connection.transaction():
            rows = await connection.fetch(
                "SELECT task_id, task_name FROM toolsdata.task_list FOR UPDATE"
            )
            match = _closest_task(rows, task_name, mutation=True)
            if match is None:
                return {"deleted": False}
            row = await connection.fetchrow(
                """
                DELETE FROM toolsdata.task_list
                WHERE task_id = $1
                RETURNING task_id, task_name
                """,
                match["task_id"],
            )
            return {"deleted": True, "task_id": row["task_id"], "task_name": row["task_name"]}
    finally:
        await connection.close()
