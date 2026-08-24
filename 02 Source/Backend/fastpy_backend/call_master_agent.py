import os
from uuid import uuid4

import httpx

from call_storage import log_event_pgsql


DEFAULT_MASTER_AGENT_URL = "http://127.0.0.1:8001"
DEFAULT_TIMEOUT_SECONDS = 300.0


class MasterAgentServiceError(RuntimeError):
    """Raised when the master-agent HTTP service cannot return a reply."""


async def invoke_master_agent(message: str) -> str:
    """Send a chat message to the master-agent microservice."""
    request_id = str(uuid4())
    base_url = os.getenv(
        "MASTER_AGENT_URL",
        DEFAULT_MASTER_AGENT_URL,
    ).rstrip("/")
    timeout_seconds = float(
        os.getenv(
            "MASTER_AGENT_TIMEOUT_SECONDS",
            str(DEFAULT_TIMEOUT_SECONDS),
        )
    )

    try:
        await log_event_pgsql(
            request_id=request_id,
            chat_message=message,
            service_name="backend",
            script_name="call_master_agent.py",
            event_type="call_master_agent",
            chat_history=[{"role": "user", "content": message}],
        )
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(
                f"{base_url}/invoke",
                json={
                    "RequestID": request_id,
                    "message": message,
                },
            )
    except httpx.RequestError as exc:
        raise MasterAgentServiceError(
            f"Could not connect to the master-agent service: {exc}"
        ) from exc

    if response.is_error:
        try:
            error_detail = response.json().get("detail", response.text)
        except ValueError:
            error_detail = response.text
        raise MasterAgentServiceError(
            "Master-agent service returned "
            f"HTTP {response.status_code}: {error_detail}"
        )

    try:
        assistant_reply = response.json()["message"]
    except (ValueError, KeyError, TypeError) as exc:
        raise MasterAgentServiceError(
            "Master-agent service returned an invalid response."
        ) from exc

    if not isinstance(assistant_reply, str) or not assistant_reply.strip():
        raise MasterAgentServiceError(
            "Master-agent service returned an empty response."
        )
    return assistant_reply.strip()
