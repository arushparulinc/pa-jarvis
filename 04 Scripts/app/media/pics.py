"""Email a random file from the root-level Google Drive Pics folder."""

import asyncio
import importlib

from ..call_storage import log_script_execution
from .google_drive import (
    delete_oldest_saved_file,
    download_random_image_from_random_subfolder,
    save_downloaded_file,
)


gmail = importlib.import_module("app.002 Comms.gmail")


@log_script_execution("media.pics")
async def run() -> dict[str, object]:
    media = await asyncio.to_thread(
        download_random_image_from_random_subfolder,
        "Pics",
    )
    saved_path = await asyncio.to_thread(save_downloaded_file, media, "pics")
    email_result = await asyncio.to_thread(
        gmail.gmail_send_email,
        "PA Jarvis: Random photo",
        (
            "Here is a random image from the Google Drive folder "
            f"{media['source_folder_name']}: {media['file_name']}"
        ),
        attachment_name=media["file_name"],
        attachment_content=media["content"],
        attachment_mime_type=media["mime_type"],
    )
    deleted_path = await asyncio.to_thread(
        delete_oldest_saved_file,
        "pics",
        exclude=saved_path,
    )
    return {
        "email": email_result,
        "saved_file": str(saved_path),
        "deleted_file": str(deleted_path) if deleted_path else None,
        "source_folder": media["source_folder_name"],
    }
