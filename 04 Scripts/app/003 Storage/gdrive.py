"""Upload generated script output to Google Drive."""

from datetime import datetime
from io import BytesIO
import os
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload


GDRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
SUPPORTED_FILE_FORMATS = {
    "csv": "text/csv",
    "json": "application/json",
    "txt": "text/plain",
}


class GoogleDriveUploadError(RuntimeError):
    """Raised when generated content cannot be uploaded to Google Drive."""


def _get_drive_service():
    credentials_value = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if not credentials_value:
        raise GoogleDriveUploadError(
            "GOOGLE_APPLICATION_CREDENTIALS is not configured."
        )

    credentials_path = Path(credentials_value)
    if not credentials_path.is_file():
        raise GoogleDriveUploadError(
            f"Google service-account file was not found at {credentials_path}."
        )

    try:
        credentials = service_account.Credentials.from_service_account_file(
            str(credentials_path),
            scopes=GDRIVE_SCOPES,
        )
        return build("drive", "v3", credentials=credentials, cache_discovery=False)
    except (OSError, ValueError) as exc:
        raise GoogleDriveUploadError(
            f"Google service-account credentials are invalid: {exc}"
        ) from exc


def upload_as_file_gdrive(
    folder_id: str,
    file_format: str,
    content: str | bytes,
    file_name: str = "",
) -> dict[str, object]:
    """Upload content as a CSV, JSON, or text file to a Google Drive folder."""
    normalized_format = file_format.strip().casefold().lstrip(".")
    if normalized_format not in SUPPORTED_FILE_FORMATS:
        raise GoogleDriveUploadError(
            "file_format must be one of: csv, json, txt."
        )

    destination_folder_id = folder_id.strip() or os.getenv(
        "GDRIVE_ROOT_FOLDER_ID", ""
    ).strip()
    if not destination_folder_id:
        raise GoogleDriveUploadError(
            "A folder_id or GDRIVE_ROOT_FOLDER_ID must be configured."
        )

    resolved_file_name = file_name.strip() or (
        f"pa_jarvis_{datetime.now():%Y%m%d_%H%M%S}.{normalized_format}"
    )
    if not resolved_file_name.casefold().endswith(f".{normalized_format}"):
        resolved_file_name = f"{resolved_file_name}.{normalized_format}"

    payload = content.encode("utf-8") if isinstance(content, str) else content
    media = MediaIoBaseUpload(
        BytesIO(payload),
        mimetype=SUPPORTED_FILE_FORMATS[normalized_format],
        resumable=False,
    )

    try:
        return _get_drive_service().files().create(
            body={"name": resolved_file_name, "parents": [destination_folder_id]},
            media_body=media,
            fields="id,name,mimeType,parents,webViewLink",
            supportsAllDrives=True,
        ).execute()
    except HttpError as exc:
        raise GoogleDriveUploadError(
            f"Google Drive could not upload {resolved_file_name}: {exc}"
        ) from exc
