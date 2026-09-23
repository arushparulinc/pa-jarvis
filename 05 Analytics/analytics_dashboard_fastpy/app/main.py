from contextlib import asynccontextmanager
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
    context: dict[str, Any] = {
        "request": request,
        "tasks": tasks,
        "shopping_items": shopping_items,
    }
    return templates.TemplateResponse(request, "dashboard.html", context)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "analytics-service"}
