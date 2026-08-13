import os

import httpx

from .call_storage import log_event_pgsql


DEFAULT_TOOLS_SERVICE_URL = "http://127.0.0.1:8003"
DEFAULT_TIMEOUT_SECONDS = 300.0


class ToolsServiceError(RuntimeError):
    """Raised when the Tools HTTP service cannot execute a tool."""


async def execute_tool(
    request_id: str,
    name: str,
    arguments: dict[str, object] | None = None,
    chat_history: list[dict[str, object]] | None = None,
) -> object:
    """Execute one named tool through the independent Tools service."""
    base_url = os.getenv(
        "TOOLS_SERVICE_URL",
        DEFAULT_TOOLS_SERVICE_URL,
    ).rstrip("/")
    timeout = float(
        os.getenv(
            "TOOLS_SERVICE_TIMEOUT_SECONDS",
            str(DEFAULT_TIMEOUT_SECONDS),
        )
    )

    try:
        await log_event_pgsql(
            request_id=request_id,
            chat_message=f"Tool {name}: {arguments or {}}",
            service_name="agents",
            script_name="call_tools.py",
            event_type="call_tools",
            chat_history=chat_history or [],
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{base_url}/execute",
                json={
                    "RequestID": request_id,
                    "name": name,
                    "arguments": arguments or {},
                    "chat_history": chat_history or [],
                },
            )
    except httpx.RequestError as exc:
        raise ToolsServiceError(
            f"Could not connect to the Tools service: {exc}"
        ) from exc

    if response.is_error:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise ToolsServiceError(
            f"Tools service returned HTTP {response.status_code}: {detail}"
        )

    try:
        return response.json()["result"]
    except (ValueError, KeyError, TypeError) as exc:
        raise ToolsServiceError(
            "Tools service returned an invalid response."
        ) from exc
