from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

from . import tool_execution
from .call_storage import log_event_pgsql


app = FastAPI(
    title="PA Jarvis Tools Service",
    description="HTTP service for executing registered tool implementations.",
    version="0.1.0",
)


class ToolExecuteRequest(BaseModel):
    request_id: UUID = Field(alias="RequestID")
    name: str = Field(min_length=1)
    arguments: dict[str, object] = Field(default_factory=dict)
    chat_history: list[dict[str, object]] = Field(default_factory=list)


class ToolExecuteResponse(BaseModel):
    result: object


@app.get("/", tags=["General"])
async def root() -> dict[str, str]:
    return {
        "message": "PA Jarvis Tools service is running.",
        "docs": "/docs",
    }


@app.get("/health", tags=["General"])
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "tools-service"}


@app.post("/execute", response_model=ToolExecuteResponse, tags=["Tools"])
async def execute(request: ToolExecuteRequest) -> ToolExecuteResponse:
    """Execute one tool by its registered function name."""
    try:
        await log_event_pgsql(
            request_id=str(request.request_id),
            chat_message=f"Tool {request.name}: {request.arguments}",
            service_name="tools",
            script_name="tools_http_service.py",
            event_type=f"Use_Tool_{request.name}",
            chat_history=request.chat_history,
        )
        result = await tool_execution.execute_tool(
            request.name,
            request.arguments,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ToolExecuteResponse(result=result)
