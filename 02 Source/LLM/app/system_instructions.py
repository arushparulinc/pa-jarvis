import asyncio
import json
import os
from functools import lru_cache
from pathlib import Path

import asyncpg


class SystemInstructionError(RuntimeError):
    """Raised when system instructions cannot be loaded from PostgreSQL."""


SYSTEM_INSTRUCTIONS_FILE = (
    Path(__file__).resolve().parents[1] / "system_instructions.txt"
)


async def refresh_system_instructions() -> None:
    """Load system instructions from PostgreSQL and write the local cache."""
    try:
        connection = await asyncpg.connect(
            host=os.getenv("PGSQL_HOSTNAME"),
            port=int(os.getenv("PGSQL_PORT", "5432")),
            user=os.getenv("PGSQL_USER"),
            password=os.getenv("PGSQL_PASSWORD"),
            database=os.getenv("PGSQL_DBNAME"),
        )
    except Exception as exc:
        raise SystemInstructionError(
            f"Could not connect to PostgreSQL for system instructions: {exc}"
        ) from exc

    try:
        rows = await connection.fetch(
            """
            SELECT
                si.agent_id,
                a.agent_name,
                a.agent_description,
                si.instrc_type,
                si.instruction,
                si.instrc_priority
            FROM llm_system_instructions AS si
            INNER JOIN agents AS a
                ON a.agent_id = si.agent_id
            ORDER BY
                si.agent_id,
                si.instrc_priority ASC NULLS LAST,
                si.instrc_type,
                si.instruction
            """
        )
    except asyncpg.UndefinedTableError as exc:
        raise SystemInstructionError(
            "PostgreSQL table 'llm_system_instructions' was not found."
        ) from exc
    except asyncpg.UndefinedColumnError as exc:
        raise SystemInstructionError(
            "PostgreSQL agent and system-instruction tables do not match "
            "the required column structure."
        ) from exc
    except Exception as exc:
        raise SystemInstructionError(
            f"Could not load system instructions: {exc}"
        ) from exc
    finally:
        await connection.close()

    if not rows:
        raise SystemInstructionError(
            "PostgreSQL table 'llm_system_instructions' is empty."
        )

    agents_by_id: dict[object, dict[str, object]] = {}
    for row in rows:
        agent_id = row["agent_id"]
        agent = agents_by_id.setdefault(
            agent_id,
            {
                "agent_id": str(agent_id),
                "agent_name": str(row["agent_name"]).strip(),
                "agent_description": str(row["agent_description"]).strip(),
                "sections": {},
            },
        )
        instruction_type = str(row["instrc_type"]).strip()
        instruction = str(row["instruction"]).strip()
        if instruction_type and instruction:
            sections = agent["sections"]
            if not isinstance(sections, dict):
                raise SystemInstructionError("Invalid instruction sections.")
            sections.setdefault(instruction_type, []).append(instruction)

    if not agents_by_id:
        raise SystemInstructionError("No usable system instructions were found.")

    agents = []
    for agent in agents_by_id.values():
        sections = agent.pop("sections")
        agent["system_instruction"] = "\n\n".join(
            f"{instruction_type}\n" + "\n".join(instructions)
            for instruction_type, instructions in sections.items()
        )
        agents.append(agent)

    SYSTEM_INSTRUCTIONS_FILE.write_text(
        json.dumps(agents, indent=2),
        encoding="utf-8",
    )


@lru_cache(maxsize=1)
def _get_cached_agents() -> list[dict[str, object]]:
    """Read the startup-generated system-instruction cache once."""
    try:
        agents = json.loads(
            SYSTEM_INSTRUCTIONS_FILE.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemInstructionError(
            f"Could not read '{SYSTEM_INSTRUCTIONS_FILE}': {exc}"
        ) from exc

    if not isinstance(agents, list) or not agents:
        raise SystemInstructionError(
            f"System-instruction cache '{SYSTEM_INSTRUCTIONS_FILE}' is "
            "empty or invalid."
        )
    return agents


def get_system_instructions(calling_agent: str) -> str:
    """Return cached system instructions for one calling agent."""
    requested_name = calling_agent.strip().casefold()
    for agent in _get_cached_agents():
        if str(agent.get("agent_name", "")).strip().casefold() == requested_name:
            system_instruction = str(
                agent.get("system_instruction", "")
            ).strip()
            if system_instruction:
                return system_instruction
            break
    raise SystemInstructionError(
        f"No system instructions were found for agent '{calling_agent}'."
    )


if __name__ == "__main__":
    asyncio.run(refresh_system_instructions())
