from datetime import UTC, datetime
from pathlib import Path
import sys
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator


SOURCE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SOURCE_ROOT))
load_dotenv(SOURCE_ROOT / "LLM" / ".env")

from LLM import GeminiConfigurationError, GeminiError, generate_reply  # noqa: E402


app = FastAPI(
    title="PA Jarvis API",
    description="Basic backend service for the PA Jarvis chatbot.",
    version="0.1.0",
)

# Allow the local Vite frontend to call the API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(max_length=2_000, examples=["Help me plan my day."])

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        message = value.strip()
        if not message:
            raise ValueError("Message must not be blank.")
        return message


class ChatResponse(BaseModel):
    id: str
    role: str = "assistant"
    message: str
    created_at: datetime


class HealthResponse(BaseModel):
    status: str
    service: str


@app.get("/", tags=["General"])
async def root() -> dict[str, str]:
    return {
        "message": "PA Jarvis API is running.",
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthResponse, tags=["General"])
async def health_check() -> HealthResponse:
    return HealthResponse(status="healthy", service="pa-jarvis-api")


@app.post("/api/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest) -> ChatResponse:
    """Accept a chat message and return a Gemini-generated response."""
    try:
        reply = await generate_reply(request.message)
    except GeminiConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GeminiError as exc:
        raise HTTPException(
            status_code=502,
            detail="The AI service could not generate a response.",
        ) from exc

    return ChatResponse(
        id=str(uuid4()),
        message=reply,
        created_at=datetime.now(UTC),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
