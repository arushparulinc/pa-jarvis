import os

import httpx


DEFAULT_TOOLS_SERVICE_URL = "http://127.0.0.1:8003"
DEFAULT_TIMEOUT_SECONDS = 300.0


class ToolsServiceError(RuntimeError):
    """Raised when the Tools HTTP service cannot execute a tool."""


async def execute_tool(
    name: str,
    arguments: dict[str, object] | None = None,
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
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{base_url}/execute",
                json={"name": name, "arguments": arguments or {}},
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
