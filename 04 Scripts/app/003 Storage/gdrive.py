"""Upload generated script output to Google Drive."""

from datetime import datetime
from io import BytesIO
import os

from google.oauth2.credentials import Credentials
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
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN", "").strip()

    missing_secrets = [
        name
        for name, value in (
            ("GOOGLE_CLIENT_ID", client_id),
            ("GOOGLE_CLIENT_SECRET", client_secret),
            ("GOOGLE_REFRESH_TOKEN", refresh_token),
        )
        if not value
    ]
    if missing_secrets:
        raise GoogleDriveUploadError(
            "Missing Google Drive OAuth configuration: "
            + ", ".join(missing_secrets)
        )

    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=GDRIVE_SCOPES,
    )

    try:
        return build("drive", "v3", credentials=credentials, cache_discovery=False)
    except (OSError, ValueError) as exc:
        raise GoogleDriveUploadError(
            f"Could not initialize the Google Drive API: {exc}"
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
