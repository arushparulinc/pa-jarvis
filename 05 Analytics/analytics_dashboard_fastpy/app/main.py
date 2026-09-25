from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import asyncpg
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.postgres import create_pool, get_high_priority_items


APP_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=APP_DIR / "templates")


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.postgres_pool = await create_pool()
    try:
        yield
    finally:
        await application.state.postgres_pool.close()


app = FastAPI(
    title="PA Jarvis Analytics",
    version="0.1.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    tasks, shopping_items = await get_high_priority_items(
        request.app.state.postgres_pool
    )
    completed_statuses = {"complete", "completed", "closed", "done", "purchased"}
    open_task_count = sum(
        str(task["task_status"]).strip().casefold() not in completed_statuses
        for task in tasks
    )
    open_shopping_count = sum(
        str(item["item_status"]).strip().casefold() not in completed_statuses
        for item in shopping_items
    )
    now = datetime.now()
    context: dict[str, Any] = {
        "request": request,
        "tasks": tasks,
        "shopping_items": shopping_items,
        "completed_statuses": completed_statuses,
        "open_task_count": open_task_count,
        "open_shopping_count": open_shopping_count,
        "task_progress": min(len(tasks) * 14, 100),
        "shopping_progress": min(len(shopping_items) * 14, 100),
        "current_date": now.strftime("%A, %B %d"),
        "generated_at": now.strftime("%I:%M %p"),
    }
    return templates.TemplateResponse(request, "dashboard.html", context)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "analytics-service"}
