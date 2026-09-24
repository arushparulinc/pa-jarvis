from datetime import datetime
from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

from .call_pgsql_db import (
    check_postgres_health,
    log_scheduler_event_pgsql,
    log_script_event_pgsql,
    log_service_event_pgsql,
    log_llm_call_pgsql,
    log_tool_call_pgsql,
)


app = FastAPI(
    title="PA Jarvis Storage Service",
    description="HTTP service for persisting request events.",
    version="0.1.0",
)


class LogEventRequest(BaseModel):
    request_id: UUID = Field(alias="RequestID")
    service_name: str
    script_name: str
    event_type: str
    chat_message: str
    chat_history: list[dict[str, object]]
    created_at: datetime


class LogEventResponse(BaseModel):
    logged: bool


class LogLLMCallRequest(BaseModel):
    request_id: UUID = Field(alias="RequestID")
    calling_agent_name: str = Field(min_length=1, max_length=100)
    message_sent: str
    message_response: str


class LogToolCallRequest(BaseModel):
    request_id: UUID = Field(alias="RequestID")
    calling_agent_name: str = Field(min_length=1, max_length=100)
    tool_name: str = Field(min_length=1, max_length=100)
    tool_arguments: str
    tool_output: str


class LogScriptEventRequest(BaseModel):
    event_name: str = Field(min_length=1, max_length=100)
    event_type: str = Field(min_length=1, max_length=100)
    script_name: str = Field(min_length=1, max_length=200)


class LogSchedulerEventRequest(BaseModel):
    event_name: str = Field(min_length=1, max_length=100)
    event_type: str = Field(min_length=1, max_length=100)
    scheduler_name: str = Field(min_length=1, max_length=200)


@app.get("/", tags=["General"])
async def root() -> dict[str, str]:
    return {
        "message": "PA Jarvis Storage service is running.",
        "docs": "/docs",
    }


@app.get("/health", tags=["General"])
async def health() -> dict[str, object]:
    try:
        await check_postgres_health()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "service": "storage-service",
                "dependencies": {"postgres": str(exc)},
            },
        ) from exc

    return {
        "status": "healthy",
        "service": "storage-service",
        "dependencies": {"postgres": "healthy"},
    }


@app.post("/log-service-event", response_model=LogEventResponse, tags=["Storage"])
async def log_event(request: LogEventRequest) -> LogEventResponse:
    try:
        await log_service_event_pgsql(
            str(request.request_id),
            request.service_name,
            request.script_name,
            request.event_type,
            request.chat_message,
            request.chat_history,
            request.created_at,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return LogEventResponse(logged=True)


@app.post("/log-script-event", response_model=LogEventResponse, tags=["Storage"])
async def log_script_event(request: LogScriptEventRequest) -> LogEventResponse:
    try:
        await log_script_event_pgsql(
            request.event_name,
            request.event_type,
            request.script_name,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return LogEventResponse(logged=True)


@app.post("/log-scheduler-event", response_model=LogEventResponse, tags=["Storage"])
async def log_scheduler_event(
    request: LogSchedulerEventRequest,
) -> LogEventResponse:
    try:
        await log_scheduler_event_pgsql(
            request.event_name,
            request.event_type,
            request.scheduler_name,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return LogEventResponse(logged=True)


@app.post("/log-llm-call", response_model=LogEventResponse, tags=["Storage"])
async def log_llm_call(request: LogLLMCallRequest) -> LogEventResponse:
    try:
        await log_llm_call_pgsql(
            str(request.request_id),
            request.calling_agent_name,
            request.message_sent,
            request.message_response,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return LogEventResponse(logged=True)


@app.post("/log-tool-call", response_model=LogEventResponse, tags=["Storage"])
async def log_tool_call(request: LogToolCallRequest) -> LogEventResponse:
    try:
        await log_tool_call_pgsql(
            str(request.request_id),
            request.calling_agent_name,
            request.tool_name,
            request.tool_arguments,
            request.tool_output,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return LogEventResponse(logged=True)
