"""Email a random file from the root-level Google Drive Pics folder."""

import asyncio
import importlib
from pathlib import Path

from ..call_storage import log_script_execution
from .google_drive import (
    download_random_image_from_random_subfolder,
    save_downloaded_file,
)


gmail = importlib.import_module("app.002 Comms.gmail")


def delete_oldest_saved_file(
    directory: Path,
    *,
    exclude: Path | None = None,
) -> Path | None:
    """Delete the oldest locally saved picture, preserving the new picture."""
    if not directory.is_dir():
        return None

    excluded_path = exclude.resolve() if exclude is not None else None
    candidates = [
        path
        for path in directory.iterdir()
        if path.is_file()
        and (excluded_path is None or path.resolve() != excluded_path)
    ]
    if not candidates:
        return None

    oldest = min(candidates, key=lambda path: (path.stat().st_mtime_ns, path.name))
    oldest.unlink()
    return oldest


@log_script_execution(
    "media.pics",
    success_event_name="Photo downloaded, emailed, and saved locally",
    success_event_type="Success",
    failure_event_type="Failed",
)
async def run() -> dict[str, object]:
    print("Downloading a random picture from Google Drive...", flush=True)
    media = await asyncio.to_thread(
        download_random_image_from_random_subfolder,
        "Pics",
    )
    print(
        f"Downloaded {media['file_name']} from {media['source_folder_name']}.",
        flush=True,
    )

    print("Emailing the downloaded picture...", flush=True)
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
    print("Picture email sent successfully.", flush=True)

    print("Saving the picture locally...", flush=True)
    saved_path = await asyncio.to_thread(save_downloaded_file, media, "pics")
    print(f"Picture saved to {saved_path}.", flush=True)

    print("Removing the oldest previously saved picture...", flush=True)
    deleted_path = await asyncio.to_thread(
        delete_oldest_saved_file,
        saved_path.parent,
        exclude=saved_path,
    )
    if deleted_path:
        print(f"Deleted {deleted_path}.", flush=True)
    else:
        print("No older picture was available to delete.", flush=True)

    return {
        "email": email_result,
        "saved_file": str(saved_path),
        "deleted_file": str(deleted_path) if deleted_path else None,
        "source_folder": media["source_folder_name"],
    }
