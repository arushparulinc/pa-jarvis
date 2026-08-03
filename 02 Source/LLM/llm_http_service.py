from pathlib import Path
import sys
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


SOURCE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE_ROOT))
load_dotenv(Path(__file__).with_name(".env"))

from LLM import gemini_chat, gemini_client, qwen_chat, qwen_client  # noqa: E402


app = FastAPI(
    title="PA Jarvis LLM Service",
    description="Provider-neutral HTTP service for Qwen and Gemini.",
    version="0.1.0",
)


class LLMInvokeRequest(BaseModel):
    provider: Literal["qwen", "gemini"]
    shared_history: list[dict[str, object]]
    system_instruction: str = Field(min_length=1)


class LLMInvokeResponse(BaseModel):
    reply: str
    tool_calls: list[dict[str, object]]


@app.get("/", tags=["General"])
async def root() -> dict[str, str]:
    return {
        "message": "PA Jarvis LLM service is running.",
        "docs": "/docs",
    }


@app.get("/health", tags=["General"])
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "llm-service"}


@app.post("/invoke", response_model=LLMInvokeResponse, tags=["LLM"])
async def invoke(request: LLMInvokeRequest) -> LLMInvokeResponse:
    """Invoke the requested LLM provider once."""
    try:
        if request.provider == "qwen":
            reply, tool_calls = await qwen_chat.route_chat_message_qwen(
                request.shared_history,
                request.system_instruction,
            )
        else:
            reply, tool_calls = await gemini_chat.route_chat_message_gemini(
                request.shared_history,
                request.system_instruction,
            )
    except (qwen_client.QwenError, gemini_client.GeminiError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return LLMInvokeResponse(reply=reply, tool_calls=tool_calls)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "llm_http_service:app",
        host="127.0.0.1",
        port=8002,
        reload=True,
    )
