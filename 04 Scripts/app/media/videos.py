"""Email a random file from the root-level Google Drive Videos folder."""

import asyncio
import importlib

from ..call_storage import log_script_execution
from .google_drive import download_random_file


gmail = importlib.import_module("app.002 Comms.gmail")


@log_script_execution("media.videos")
async def run() -> dict[str, str]:
    media = await asyncio.to_thread(download_random_file, "Videos")
    return await asyncio.to_thread(
        gmail.gmail_send_email,
        "PA Jarvis: Random video",
        f"Here is a random file from the Google Drive Videos folder: {media['file_name']}",
        attachment_name=media["file_name"],
        attachment_content=media["content"],
        attachment_mime_type=media["mime_type"],
    )
