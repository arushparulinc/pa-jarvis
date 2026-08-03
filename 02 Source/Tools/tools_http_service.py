from pathlib import Path
import sys

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


SOURCE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE_ROOT))
load_dotenv(Path(__file__).with_name(".env"))

from Tools import tool_execution  # noqa: E402


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "tools_http_service:app",
        host="127.0.0.1",
        port=8003,
        reload=True,
    )
