"""Google Drive access shared by scheduled media jobs."""

from io import BytesIO
import os
from pathlib import Path
import secrets

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload


AK_GDRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


class AKGoogleDriveError(RuntimeError):
    """Raised when scheduled media cannot be read from Google Drive."""


def _data_subdirectory(subdirectory: str) -> Path:
    data_dir = os.getenv("AK_DATA_DIR", "").strip()
    if not data_dir:
        raise AKGoogleDriveError("AK_DATA_DIR is not configured.")
    return Path(data_dir) / subdirectory


def save_downloaded_file(media: dict[str, object], subdirectory: str) -> Path:
    """Persist downloaded media beneath the configured shared data directory."""
    file_name = Path(str(media["file_name"])).name
    if not file_name:
        raise AKGoogleDriveError("The downloaded Google Drive file has no valid name.")

    content = media.get("content")
    if not isinstance(content, bytes):
        raise AKGoogleDriveError("The downloaded Google Drive file has no byte content.")

    destination_dir = _data_subdirectory(subdirectory)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / file_name
    destination.write_bytes(content)
    return destination


def delete_oldest_saved_file(
    subdirectory: str,
    *,
    exclude: Path | None = None,
) -> Path | None:
    """Delete the oldest saved file, preserving an optional newly saved file."""
    destination_dir = _data_subdirectory(subdirectory)
    if not destination_dir.is_dir():
        return None

    excluded_path = exclude.resolve() if exclude is not None else None
    candidates = [
        path
        for path in destination_dir.iterdir()
        if path.is_file()
        and (excluded_path is None or path.resolve() != excluded_path)
    ]
    if not candidates:
        return None

    oldest = min(candidates, key=lambda path: (path.stat().st_mtime_ns, path.name))
    oldest.unlink()
    return oldest


def _escape_query_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _get_drive_service():
    client_id = os.getenv("AK_GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("AK_GOOGLE_CLIENT_SECRET", "").strip()
    refresh_token = os.getenv("AK_GOOGLE_REFRESH_TOKEN", "").strip()
    missing = [
        name
        for name, value in (
            ("AK_GOOGLE_CLIENT_ID", client_id),
            ("AK_GOOGLE_CLIENT_SECRET", client_secret),
            ("AK_GOOGLE_REFRESH_TOKEN", refresh_token),
        )
        if not value
    ]
    if missing:
        raise AKGoogleDriveError(
            "Missing Google Drive OAuth configuration: " + ", ".join(missing)
        )

    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=AK_GDRIVE_SCOPES,
    )

    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def _find_named_folder(service, parent_id: str, folder_name: str) -> dict[str, str]:
    result = service.files().list(
        q=(
            f"'{_escape_query_value(parent_id)}' in parents and "
            f"name = '{_escape_query_value(folder_name)}' and "
            "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        ),
        spaces="drive",
        fields="files(id,name)",
        pageSize=2,
    ).execute()
    folders = result.get("files", [])
    if not folders:
        raise AKGoogleDriveError(
            f"Google Drive folder {folder_name!r} was not found under the configured root."
        )
    if len(folders) > 1:
        raise AKGoogleDriveError(
            f"Multiple Google Drive folders named {folder_name!r} were found under the configured root."
        )
    return folders[0]


def _list_folder_items(
    service,
    folder_id: str,
    *,
    folders_only: bool = False,
) -> list[dict[str, str]]:
    mime_query = (
        "mimeType = 'application/vnd.google-apps.folder'"
        if folders_only
        else "mimeType != 'application/vnd.google-apps.folder'"
    )
    items: list[dict[str, str]] = []
    page_token = None
    while True:
        result = service.files().list(
            q=(
                f"'{_escape_query_value(folder_id)}' in parents and "
                f"{mime_query} and trashed = false"
            ),
            spaces="drive",
            fields="nextPageToken,files(id,name,mimeType)",
            pageSize=1000,
            pageToken=page_token,
        ).execute()
        items.extend(result.get("files", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            return items


def _download_file(service, selected: dict[str, str]) -> dict[str, object]:
    buffer = BytesIO()
    downloader = MediaIoBaseDownload(
        buffer,
        service.files().get_media(fileId=selected["id"]),
    )
    done = False
    while not done:
        _, done = downloader.next_chunk()

    return {
        "file_id": selected["id"],
        "file_name": selected["name"],
        "mime_type": selected.get("mimeType") or "application/octet-stream",
        "content": buffer.getvalue(),
    }


def download_random_image_from_random_subfolder(
    folder_name: str,
) -> dict[str, object]:
    """Download a random image from a random immediate child folder."""
    root_folder_id = os.getenv("AK_GDRIVE_ROOT_FOLDER", "").strip()
    if not root_folder_id:
        raise AKGoogleDriveError("AK_GDRIVE_ROOT_FOLDER is not configured.")

    try:
        service = _get_drive_service()
        parent_folder = _find_named_folder(service, root_folder_id, folder_name)
        child_folders = _list_folder_items(
            service,
            parent_folder["id"],
            folders_only=True,
        )
        if not child_folders:
            raise AKGoogleDriveError(
                f"Google Drive folder {folder_name!r} contains no subfolders."
            )

        selected_folder = secrets.choice(child_folders)
        image_files = [
            item
            for item in _list_folder_items(service, selected_folder["id"])
            if (item.get("mimeType") or "").startswith("image/")
        ]
        if not image_files:
            raise AKGoogleDriveError(
                f"Google Drive folder {selected_folder['name']!r} contains no image files."
            )

        result = _download_file(service, secrets.choice(image_files))
        result["source_folder_name"] = selected_folder["name"]
        return result
    except HttpError as exc:
        raise AKGoogleDriveError(
            f"Google Drive could not provide a random image from {folder_name!r}: {exc}"
        ) from exc


def download_random_file(folder_name: str) -> dict[str, object]:
    """Download one random non-folder file from a named root-level folder."""
    root_folder_id = os.getenv("AK_GDRIVE_ROOT_FOLDER", "").strip()
    if not root_folder_id:
        raise AKGoogleDriveError("AK_GDRIVE_ROOT_FOLDER is not configured.")

    try:
        service = _get_drive_service()
        folder = _find_named_folder(service, root_folder_id, folder_name)
        files = _list_folder_items(service, folder["id"])

        if not files:
            raise AKGoogleDriveError(f"Google Drive folder {folder_name!r} contains no files.")

        return _download_file(service, secrets.choice(files))
    except HttpError as exc:
        raise AKGoogleDriveError(
            f"Google Drive could not provide a random file from {folder_name!r}: {exc}"
        ) from exc
