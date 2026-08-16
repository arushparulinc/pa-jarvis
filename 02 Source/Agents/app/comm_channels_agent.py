from .sub_agent_runtime import run_sub_agent


CALLING_AGENT = "Comm Channnel Agent"


async def route_agent_message(request_id: str, original_user_prompt: str) -> str:
    """Run the stateless communication-channels sub-agent."""
    return await run_sub_agent(
        request_id,
        original_user_prompt,
        CALLING_AGENT,
        "comm_channels_agent.py",
    )
