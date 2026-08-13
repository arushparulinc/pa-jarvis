from datetime import datetime
from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

from .call_pgsql_db import log_event_pgsql


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
    created_at: datetime


class LogEventResponse(BaseModel):
    logged: bool


@app.get("/", tags=["General"])
async def root() -> dict[str, str]:
    return {
        "message": "PA Jarvis Storage service is running.",
        "docs": "/docs",
    }


@app.get("/health", tags=["General"])
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "storage-service"}


@app.post("/log-event", response_model=LogEventResponse, tags=["Storage"])
async def log_event(request: LogEventRequest) -> LogEventResponse:
    try:
        await log_event_pgsql(
            str(request.request_id),
            request.service_name,
            request.script_name,
            request.event_type,
            request.chat_message,
            request.created_at,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return LogEventResponse(logged=True)
