from collections.abc import Awaitable, Callable

from . import (
    comm_channels_agent,
    google_drive_agent,
    internet_tools_agent,
    personal_tools_agent,
)


AgentHandler = Callable[[str, str], Awaitable[str]]

AGENT_HANDLERS: dict[str, AgentHandler] = {
    "google_drive_agent": google_drive_agent.route_agent_message,
    "personal_tools_agent": personal_tools_agent.route_agent_message,
    "comm_channels_agent": comm_channels_agent.route_agent_message,
    "internet_tools_agent": internet_tools_agent.route_agent_message,
}


async def execute_agent_actions(
    request_id: str,
    agent_name: str,
    original_user_prompt: str,
) -> str:
    """Dispatch a master-router tool call to a stateless sub-agent."""
    handler = AGENT_HANDLERS.get(agent_name)
    if handler is None:
        raise KeyError(f"Unknown sub-agent: {agent_name}")
    return await handler(request_id, original_user_prompt)
