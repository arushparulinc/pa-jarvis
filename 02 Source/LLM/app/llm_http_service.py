from pathlib import Path
from typing import Literal
from uuid import UUID

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

from . import (
    gemini_chat,
    gemini_client,
    qwen_chat,
    qwen_client,
    system_instructions,
    tools_registry,
)
from .call_storage import log_event_pgsql


app = FastAPI(
    title="PA Jarvis LLM Service",
    description="Provider-neutral HTTP service for Qwen and Gemini.",
    version="0.1.0",
)


class LLMInvokeRequest(BaseModel):
    request_id: UUID = Field(alias="RequestID")
    provider: Literal["qwen", "gemini"]
    shared_history: list[dict[str, object]]


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
        message = (
            str(request.shared_history[-1].get("content", ""))
            if request.shared_history
            else ""
        )
        await log_event_pgsql(
            request_id=str(request.request_id),
            chat_message=message,
            service_name="llm",
            script_name="llm_http_service.py",
            event_type=f"Use_LLM_{request.provider}",
            chat_history=request.shared_history,
        )
        if request.provider == "qwen":
            reply, tool_calls = await qwen_chat.route_chat_message_qwen(
                request.shared_history,
            )
        else:
            reply, tool_calls = await gemini_chat.route_chat_message_gemini(
                request.shared_history,
            )
    except (
        qwen_client.QwenError,
        gemini_client.GeminiError,
        system_instructions.SystemInstructionError,
        tools_registry.ToolsRegistryError,
    ) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return LLMInvokeResponse(reply=reply, tool_calls=tool_calls)
