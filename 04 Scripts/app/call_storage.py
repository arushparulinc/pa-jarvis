"""HTTP client for event logging owned by the Storage service."""

from collections.abc import Callable
from functools import wraps
import inspect
import os
from typing import Any

import httpx


STORAGE_SERVICE_URL = os.getenv("STORAGE_SERVICE_URL", "http://storage:8004").rstrip("/")


async def log_scheduler_event(
    event_name: str,
    event_type: str,
    scheduler_name: str,
) -> None:
    """Ask Storage to persist a scheduler event in PostgreSQL."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{STORAGE_SERVICE_URL}/log-scheduler-event",
            json={
                "event_name": event_name,
                "event_type": event_type,
                "scheduler_name": scheduler_name,
            },
        )
        response.raise_for_status()


async def log_script_event(
    event_name: str,
    event_type: str,
    script_name: str,
) -> None:
    """Ask Storage to persist a script execution event in PostgreSQL."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{STORAGE_SERVICE_URL}/log-script-event",
            json={
                "event_name": event_name,
                "event_type": event_type,
                "script_name": script_name,
            },
        )
        response.raise_for_status()


def log_script_execution(script_name: str):
    """Record the outcome of every invocation of a scheduled script."""
    def decorator(function: Callable[..., Any]):
        @wraps(function)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                result = function(*args, **kwargs)
                if inspect.isawaitable(result):
                    result = await result
            except Exception:
                await log_script_event(
                    event_name="Execution failed",
                    event_type="Failed",
                    script_name=script_name,
                )
                raise

            await log_script_event(
                event_name="Execution completed",
                event_type="Success",
                script_name=script_name,
            )
            return result

        return wrapper

    return decorator
