"""Google Drive access shared by scheduled media jobs."""

from io import BytesIO
import os
from pathlib import Path
import secrets

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload


AK_GDRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


class AKGoogleDriveError(RuntimeError):
    """Raised when scheduled media cannot be read from Google Drive."""


def _escape_query_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _get_drive_service():
    credentials_value = os.getenv("AK_GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if not credentials_value:
        raise AKGoogleDriveError("AK_GOOGLE_APPLICATION_CREDENTIALS is not configured.")

    credentials_path = Path(credentials_value)
    if not credentials_path.is_file():
        raise AKGoogleDriveError(
            f"Google service-account file was not found at {credentials_path}."
        )

    try:
        credentials = service_account.Credentials.from_service_account_file(
            str(credentials_path),
            scopes=AK_GDRIVE_SCOPES,
        )
    except (OSError, ValueError) as exc:
        raise AKGoogleDriveError(
            f"Google service-account credentials are invalid: {exc}"
        ) from exc

    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def download_random_file(folder_name: str) -> dict[str, object]:
    """Download one random non-folder file from a named root-level folder."""
    root_folder_id = os.getenv("AK_GDRIVE_ROOT_FOLDER", "").strip()
    if not root_folder_id:
        raise AKGoogleDriveError("AK_GDRIVE_ROOT_FOLDER is not configured.")

    try:
        service = _get_drive_service()
        folder_result = service.files().list(
            q=(
                f"'{_escape_query_value(root_folder_id)}' in parents and "
                f"name = '{_escape_query_value(folder_name)}' and "
                "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
            ),
            spaces="drive",
            fields="files(id,name)",
            pageSize=2,
        ).execute()
        folders = folder_result.get("files", [])
        if not folders:
            raise AKGoogleDriveError(
                f"Google Drive folder {folder_name!r} was not found under the configured root."
            )
        if len(folders) > 1:
            raise AKGoogleDriveError(
                f"Multiple Google Drive folders named {folder_name!r} were found under the configured root."
            )

        files: list[dict[str, str]] = []
        page_token = None
        while True:
            result = service.files().list(
                q=(
                    f"'{_escape_query_value(folders[0]['id'])}' in parents and "
                    "mimeType != 'application/vnd.google-apps.folder' and trashed = false"
                ),
                spaces="drive",
                fields="nextPageToken,files(id,name,mimeType)",
                pageSize=1000,
                pageToken=page_token,
            ).execute()
            files.extend(result.get("files", []))
            page_token = result.get("nextPageToken")
            if not page_token:
                break

        if not files:
            raise AKGoogleDriveError(f"Google Drive folder {folder_name!r} contains no files.")

        selected = secrets.choice(files)
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
    except HttpError as exc:
        raise AKGoogleDriveError(
            f"Google Drive could not provide a random file from {folder_name!r}: {exc}"
        ) from exc
