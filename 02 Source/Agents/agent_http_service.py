from pathlib import Path
import sys

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator


# Make the sibling LLM and Tools packages importable when this service is
# launched directly from the Agents folder.
SOURCE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE_ROOT))
load_dotenv(Path(__file__).with_name(".env"))

from Agents import ChatError, route_chat_message  # noqa: E402


app = FastAPI(
    title="PA Jarvis Master Agent Service",
    description="HTTP service for invoking the master router agent.",
    version="0.1.0",
)


class InvokeRequest(BaseModel):
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
        assistant_reply = await route_chat_message(request.message)
    except ChatError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return InvokeResponse(message=assistant_reply)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "agent_http_service:app",
        host="127.0.0.1",
        port=8001,
        reload=True,
    )
