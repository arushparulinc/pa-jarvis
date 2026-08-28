from . import sub_agent_runtime

CALLING_AGENTS = {
    "google_drive_agent": "Google Drive Agent",
    "personal_tools_agent": "Personal Tools Agent",
    "comm_channels_agent": "Comm Channels Agent",
    "internet_tools_agent": "Internet Tools Agent",
    "planner_agent": "Planner Agent",
    "shopping_agent": "Shopping Agent",
}


async def execute_agent_actions(
    request_id: str,
    agent_name: str,
    agent_instructions: str,
) -> str:
    """Dispatch a master-router tool call to a stateless sub-agent."""
    calling_agent = CALLING_AGENTS.get(agent_name)
    if calling_agent is None:
        raise KeyError(f"Unknown sub-agent: {agent_name}")
    return await sub_agent_runtime.run_sub_agent(
        request_id=request_id,
        agent_instructions=agent_instructions,
        calling_agent=calling_agent,
        script_name="call_sub_agent.py",
    )
