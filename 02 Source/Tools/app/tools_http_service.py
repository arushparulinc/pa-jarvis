from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

from . import tool_execution


app = FastAPI(
    title="PA Jarvis Tools Service",
    description="HTTP service for executing registered tool implementations.",
    version="0.1.0",
)


class ToolExecuteRequest(BaseModel):
    name: str = Field(min_length=1)
    arguments: dict[str, object] = Field(default_factory=dict)


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
        result = await tool_execution.execute_tool(
            request.name,
            request.arguments,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ToolExecuteResponse(result=result)
