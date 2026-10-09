from contextlib import asynccontextmanager
from datetime import datetime
import mimetypes
import os
from pathlib import Path
from typing import Any

import asyncpg
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.postgres import create_pool, get_high_priority_items


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("AK_DATA_DIR", "/app/data"))
templates = Jinja2Templates(directory=APP_DIR / "templates")


def _available_pictures() -> list[Path]:
    """Return locally saved image files ordered from newest to oldest."""
    pics_dir = DATA_DIR / "pics"
    if not pics_dir.is_dir():
        return []

    pictures = [
        path
        for path in pics_dir.iterdir()
        if path.is_file()
        and (mimetypes.guess_type(path.name)[0] or "").startswith("image/")
    ]
    return sorted(
        pictures,
        key=lambda path: (path.stat().st_mtime, path.name),
        reverse=True,
    )


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


@app.get("/tv", response_class=HTMLResponse)
async def tv_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="tv.html",
        context={},
    )


@app.get("/media/pics/latest", response_class=FileResponse)
async def latest_picture() -> FileResponse:
    """Return the most recently saved picture from the shared data volume."""
    pictures = _available_pictures()
    if not pictures:
        raise HTTPException(status_code=404, detail="No saved pictures are available.")

    return FileResponse(
        pictures[0],
        headers={"Cache-Control": "no-store"},
    )


@app.get("/media/pics")
async def list_pictures() -> dict[str, list[str]]:
    """Return opaque URLs for every locally saved picture."""
    pictures = _available_pictures()
    return {
        "pictures": [f"/media/pics/{index}" for index in range(len(pictures))]
    }


@app.get("/media/pics/{picture_index}", response_class=FileResponse)
async def indexed_picture(picture_index: int) -> FileResponse:
    """Return one picture by its position in the newest-first inventory."""
    pictures = _available_pictures()
    if picture_index < 0 or picture_index >= len(pictures):
        raise HTTPException(status_code=404, detail="Picture was not found.")

    return FileResponse(
        pictures[picture_index],
        headers={"Cache-Control": "no-store"},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "analytics-service"}
