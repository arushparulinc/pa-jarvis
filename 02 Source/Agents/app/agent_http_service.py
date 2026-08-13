from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

from .master_router_agent import ChatError, route_chat_message
from .call_storage import log_event_pgsql


app = FastAPI(
    title="PA Jarvis Master Agent Service",
    description="HTTP service for invoking the master router agent.",
    version="0.1.0",
)


class InvokeRequest(BaseModel):
    request_id: UUID = Field(alias="RequestID")
    message: str = Field(max_length=2_000)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        message = value.strip()
        if not message:
            raise ValueError("Message must not be blank.")
        return message


class InvokeResponse(BaseModel):
    message: str


@app.get("/", tags=["General"])
async def root() -> dict[str, str]:
    return {
        "message": "PA Jarvis Agents service is running.",
        "docs": "/docs",
    }


@app.get("/health", tags=["General"])
async def health() -> dict[str, str]:
    return {
        "status": "healthy",
        "service": "master-agent-service",
    }


@app.post("/invoke", response_model=InvokeResponse, tags=["Agent"])
async def invoke(request: InvokeRequest) -> InvokeResponse:
    """Invoke the master router with one user message."""
    try:
        await log_event_pgsql(
            request_id=str(request.request_id),
            chat_message=request.message,
            service_name="agents",
            script_name="agent_http_service.py",
            event_type="call_master_router",
        )
        assistant_reply = await route_chat_message(
            str(request.request_id),
            request.message,
        )
    except ChatError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return InvokeResponse(message=assistant_reply)
