import json
import os
from datetime import datetime

import asyncpg


async def log_event_pgsql(
    request_id: str,
    service_name: str,
    script_name: str,
    event_type: str,
    chat_message: str,
    chat_history: list[dict[str, object]],
    created_at: datetime,
) -> None:
    """Insert one event into the PA Jarvis service-events table."""
    connection = await asyncpg.connect(
        host=os.getenv("PGSQL_HOSTNAME"),
        port=int(os.getenv("PGSQL_PORT", "5432")),
        user=os.getenv("PGSQL_USER"),
        password=os.getenv("PGSQL_PASSWORD"),
        database=os.getenv("PGSQL_DBNAME"),
    )
    try:
        await connection.execute(
            """
            INSERT INTO pa_jarvis_service_events (
                request_id,
                service_name,
                script_name,
                event_type,
                chat_message,
                chat_history,
                created_at
            )
            VALUES ($1::uuid, $2, $3, $4, $5, $6::jsonb, $7)
            """,
            request_id,
            service_name,
            script_name,
            event_type,
            chat_message,
            json.dumps(chat_history, default=str),
            created_at,
        )
    except asyncpg.UndefinedTableError as exc:
        raise RuntimeError(
            "PostgreSQL table 'pa_jarvis_service_events' was not found."
        ) from exc
    except asyncpg.UndefinedColumnError as exc:
        raise RuntimeError(
            "PostgreSQL table 'pa_jarvis_service_events' does not match "
            "the required event-log structure."
        ) from exc
    finally:
        await connection.close()


async def log_llm_call_pgsql(
    request_id: str,
    calling_agent_name: str,
    message_sent: str,
    message_response: str,
) -> None:
    """Insert one raw LLM request and response into PostgreSQL."""
    connection = await asyncpg.connect(
        host=os.getenv("PGSQL_HOSTNAME"),
        port=int(os.getenv("PGSQL_PORT", "5432")),
        user=os.getenv("PGSQL_USER"),
        password=os.getenv("PGSQL_PASSWORD"),
        database=os.getenv("PGSQL_DBNAME"),
    )
    try:
        await connection.execute(
            """
            INSERT INTO pa_jarvis_llm_calls (
                request_id,
                calling_agent_name,
                message_sent,
                message_response
            )
            VALUES ($1::uuid, $2, $3, $4)
            """,
            request_id,
            calling_agent_name,
            message_sent,
            message_response,
        )
    except asyncpg.UndefinedTableError as exc:
        raise RuntimeError(
            "PostgreSQL table 'pa_jarvis_llm_calls' was not found."
        ) from exc
    except asyncpg.UndefinedColumnError as exc:
        raise RuntimeError(
            "PostgreSQL table 'pa_jarvis_llm_calls' does not match the "
            "required LLM-call structure."
        ) from exc
    finally:
        await connection.close()


async def log_tool_call_pgsql(
    request_id: str,
    calling_agent_name: str,
    tool_name: str,
    tool_arguments: str,
    tool_output: str,
) -> None:
    """Insert one raw tool request and output into PostgreSQL."""
    connection = await asyncpg.connect(
        host=os.getenv("PGSQL_HOSTNAME"),
        port=int(os.getenv("PGSQL_PORT", "5432")),
        user=os.getenv("PGSQL_USER"),
        password=os.getenv("PGSQL_PASSWORD"),
        database=os.getenv("PGSQL_DBNAME"),
    )
    try:
        await connection.execute(
            """
            INSERT INTO pa_jarvis_tool_calls (
                request_id,
                calling_agent_name,
                tool_name,
                tool_arguments,
                tool_output
            )
            VALUES ($1::uuid, $2, $3, $4, $5)
            """,
            request_id,
            calling_agent_name,
            tool_name,
            tool_arguments,
            tool_output,
        )
    except asyncpg.UndefinedTableError as exc:
        raise RuntimeError(
            "PostgreSQL table 'pa_jarvis_tool_calls' was not found."
        ) from exc
    except asyncpg.UndefinedColumnError as exc:
        raise RuntimeError(
            "PostgreSQL table 'pa_jarvis_tool_calls' does not match the "
            "required tool-call structure."
        ) from exc
    finally:
        await connection.close()
