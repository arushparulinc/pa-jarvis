import os
from datetime import UTC, datetime

import httpx


DEFAULT_STORAGE_SERVICE_URL = "http://127.0.0.1:8004"
DEFAULT_TIMEOUT_SECONDS = 30.0


async def log_event_pgsql(
    request_id: str,
    chat_message: str,
    service_name: str,
    script_name: str,
    event_type: str,
    created_at: datetime | None = None,
) -> bool:
    """Send one event to the independent Storage service."""
    base_url = os.getenv(
        "STORAGE_SERVICE_URL",
        DEFAULT_STORAGE_SERVICE_URL,
    ).rstrip("/")
    payload = {
        "RequestID": request_id,
        "chat_message": chat_message,
        "service_name": service_name,
        "script_name": script_name,
        "event_type": event_type,
        "created_at": (created_at or datetime.now(UTC)).isoformat(),
    }

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
            response = await client.post(f"{base_url}/log-event", json=payload)
        return response.is_success
    except httpx.RequestError:
        return False
