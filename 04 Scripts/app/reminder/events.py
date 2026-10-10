"""Synchronize the next seven days of Google Calendar events to PostgreSQL."""

import asyncio
from datetime import UTC, date, datetime, time, timedelta
import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import asyncpg
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..call_storage import log_script_execution


# Match planner_tools so the existing OAuth refresh token can be reused.
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]
DEFAULT_CALENDAR_ID = "primary"
DEFAULT_TIME_ZONE = "America/Toronto"


class CalendarSyncError(RuntimeError):
    """Raised when upcoming calendar events cannot be synchronized."""


async def _connect_postgres() -> asyncpg.Connection:
    return await asyncpg.connect(
        host=os.getenv("PGSQL_HOSTNAME"),
        port=int(os.getenv("PGSQL_PORT", "5432")),
        user=os.getenv("PGSQL_USER"),
        password=os.getenv("PGSQL_PASSWORD"),
        database=os.getenv("PGSQL_DBNAME"),
    )


def _get_calendar_service():
    client_id = os.getenv("AK_GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("AK_GOOGLE_CLIENT_SECRET", "").strip()
    refresh_token = os.getenv("AK_GOOGLE_REFRESH_TOKEN", "").strip()
    missing = [
        name
        for name, value in (
            ("AK_GOOGLE_CLIENT_ID", client_id),
            ("AK_GOOGLE_CLIENT_SECRET", client_secret),
            ("AK_GOOGLE_REFRESH_TOKEN", refresh_token),
        )
        if not value
    ]
    if missing:
        raise CalendarSyncError(
            "Missing Google Calendar OAuth configuration: " + ", ".join(missing)
        )

    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=CALENDAR_SCOPES,
    )
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def _list_upcoming_events(
    calendar_id: str,
    start: datetime,
    end: datetime,
) -> list[dict[str, object]]:
    """Fetch every event instance in the requested interval."""
    service = _get_calendar_service()
    events: list[dict[str, object]] = []
    page_token = None
    try:
        while True:
            response = service.events().list(
                calendarId=calendar_id,
                timeMin=start.isoformat().replace("+00:00", "Z"),
                timeMax=end.isoformat().replace("+00:00", "Z"),
                singleEvents=True,
                orderBy="startTime",
                showDeleted=False,
                maxResults=2500,
                pageToken=page_token,
            ).execute()
            events.extend(response.get("items", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                return events
    except HttpError as exc:
        raise CalendarSyncError(
            f"Google Calendar could not list upcoming events: {exc}"
        ) from exc


def _event_datetime(value: dict[str, str]) -> tuple[datetime, bool]:
    """Normalize either a Calendar dateTime or all-day date to an aware datetime."""
    if value.get("dateTime"):
        parsed = datetime.fromisoformat(value["dateTime"].replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            try:
                parsed = parsed.replace(
                    tzinfo=ZoneInfo(value.get("timeZone") or DEFAULT_TIME_ZONE)
                )
            except ZoneInfoNotFoundError as exc:
                raise CalendarSyncError(
                    f"Unknown Google Calendar time zone: {value.get('timeZone')}"
                ) from exc
        return parsed, False

    if value.get("date"):
        return (
            datetime.combine(
                date.fromisoformat(value["date"]),
                time.min,
                tzinfo=ZoneInfo(DEFAULT_TIME_ZONE),
            ),
            True,
        )

    raise CalendarSyncError("A Google Calendar event has no start or end time.")


def _event_record(event: dict[str, object]) -> tuple[object, ...]:
    start_at, is_all_day = _event_datetime(event.get("start", {}))
    end_at, _ = _event_datetime(event.get("end", {}))
    return (
        str(event["id"]),
        str(event.get("summary") or "(No title)"),
        str(event.get("description") or "") or None,
        start_at,
        end_at,
        is_all_day,
    )


@log_script_execution("reminder.events")
async def run() -> dict[str, object]:
    """Replace the PostgreSQL calendar cache with events from the next seven days."""
    calendar_id = os.getenv("GOOGLE_CALENDAR_ID", DEFAULT_CALENDAR_ID).strip()
    start = datetime.now(UTC)
    end = start + timedelta(days=7)
    events = await asyncio.to_thread(
        _list_upcoming_events,
        calendar_id,
        start,
        end,
    )
    records = [_event_record(event) for event in events]

    connection = await _connect_postgres()
    try:
        async with connection.transaction():
            await connection.execute("DELETE FROM toolsdata.google_calendar_events")
            if records:
                await connection.executemany(
                    """
                    INSERT INTO toolsdata.google_calendar_events (
                        google_event_id,
                        event_name,
                        event_description,
                        start_at,
                        end_at,
                        is_all_day
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    records,
                )
    finally:
        await connection.close()

    return {
        "status": "synchronized",
        "calendar_id": calendar_id,
        "event_count": len(records),
        "range_start": start.isoformat(),
        "range_end": end.isoformat(),
    }
