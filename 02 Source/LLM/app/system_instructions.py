import asyncio
import os
from collections import defaultdict
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
            SELECT instrc_type, instruction, instrc_priority
            FROM llm_system_instructions
            ORDER BY instrc_priority ASC NULLS LAST, instrc_type, instruction
            """
        )
    except asyncpg.UndefinedTableError as exc:
        raise SystemInstructionError(
            "PostgreSQL table 'llm_system_instructions' was not found."
        ) from exc
    except asyncpg.UndefinedColumnError as exc:
        raise SystemInstructionError(
            "PostgreSQL table 'llm_system_instructions' must contain "
            "'instrc_type', 'instruction', and 'instrc_priority' columns."
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

    sections: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        instruction_type = str(row["instrc_type"]).strip()
        instruction = str(row["instruction"]).strip()
        if instruction_type and instruction:
            sections[instruction_type].append(instruction)

    if not sections:
        raise SystemInstructionError("No usable system instructions were found.")

    system_instruction = "\n\n".join(
        f"{instruction_type}\n" + "\n".join(instructions)
        for instruction_type, instructions in sections.items()
    )
    SYSTEM_INSTRUCTIONS_FILE.write_text(
        system_instruction,
        encoding="utf-8",
    )


@lru_cache(maxsize=1)
def get_system_instructions() -> str:
    """Read the startup-generated system-instruction cache once."""
    try:
        system_instruction = SYSTEM_INSTRUCTIONS_FILE.read_text(
            encoding="utf-8"
        ).strip()
    except OSError as exc:
        raise SystemInstructionError(
            f"Could not read '{SYSTEM_INSTRUCTIONS_FILE}': {exc}"
        ) from exc

    if not system_instruction:
        raise SystemInstructionError(
            f"System-instruction cache '{SYSTEM_INSTRUCTIONS_FILE}' is empty."
        )
    return system_instruction


if __name__ == "__main__":
    asyncio.run(refresh_system_instructions())
