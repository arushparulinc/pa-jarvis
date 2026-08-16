import asyncio
from io import BytesIO
from pathlib import Path
import threading

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

CREDENTIALS_FOLDER = Path(__file__).resolve().parents[1] / "credentials"
GDRIVE_CLIENT_SECRET_PATH = (
    CREDENTIALS_FOLDER / "gdrive_client_secret.json"
)
GDRIVE_TOKEN_PATH = CREDENTIALS_FOLDER / "gdrive_token.json"
GDRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
credentials_lock = threading.Lock()


class GoogleDriveError(RuntimeError):
    """Raised when a Google Drive operation cannot be completed."""


def _get_drive_service():
    """Create an authorized Drive client and persist refreshed OAuth tokens."""
    with credentials_lock:
        CREDENTIALS_FOLDER.mkdir(parents=True, exist_ok=True)
        credentials = None

        if GDRIVE_TOKEN_PATH.exists():
            credentials = Credentials.from_authorized_user_file(
                str(GDRIVE_TOKEN_PATH),
                GDRIVE_SCOPES,
            )

        if not credentials or not credentials.valid:
            if (
                credentials
                and credentials.expired
                and credentials.refresh_token
            ):
                credentials.refresh(GoogleAuthRequest())
            else:
                if not GDRIVE_CLIENT_SECRET_PATH.exists():
                    raise GoogleDriveError(
                        "Google Drive OAuth client secret was not found at "
                        f"{GDRIVE_CLIENT_SECRET_PATH}."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(GDRIVE_CLIENT_SECRET_PATH),
                    GDRIVE_SCOPES,
                )
                credentials = flow.run_local_server(port=0)

            GDRIVE_TOKEN_PATH.write_text(
                credentials.to_json(),
                encoding="utf-8",
            )

    return build(
        "drive",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )


async def gdrive_read(file_id: str) -> str:
    """Read the contents of a specific file from Google Drive."""
    def read_file() -> str:
        try:
            service = _get_drive_service()
            metadata = service.files().get(
                fileId=file_id,
                fields="id,name,mimeType",
                supportsAllDrives=True,
            ).execute()
            mime_type = metadata["mimeType"]

            export_types = {
                "application/vnd.google-apps.document": "text/plain",
                "application/vnd.google-apps.spreadsheet": "text/csv",
                "application/vnd.google-apps.presentation": "text/plain",
            }
            if mime_type in export_types:
                request = service.files().export_media(
                    fileId=file_id,
                    mimeType=export_types[mime_type],
                )
            else:
                request = service.files().get_media(
                    fileId=file_id,
                    supportsAllDrives=True,
                )

            content = BytesIO()
            downloader = MediaIoBaseDownload(content, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            return content.getvalue().decode("utf-8", errors="replace")
        except HttpError as exc:
            raise GoogleDriveError(
                f"Google Drive could not read file {file_id}: {exc}"
            ) from exc

    return await asyncio.to_thread(read_file)


async def gdrive_write(
    local_file_path: str,
    folder_id: str,
    file_name: str = "",
) -> dict[str, object]:
    """Upload a local file into a specific Google Drive folder."""
    source_path = Path(local_file_path).expanduser().resolve()
    if not source_path.is_file():
        raise GoogleDriveError(f"Local file does not exist: {source_path}")

    def upload_file() -> dict[str, object]:
        try:
            service = _get_drive_service()
            metadata = {
                "name": file_name.strip() or source_path.name,
                "parents": [folder_id],
            }
            media = MediaFileUpload(str(source_path), resumable=False)
            return service.files().create(
                body=metadata,
                media_body=media,
                fields="id,name,mimeType,parents,webViewLink",
                supportsAllDrives=True,
            ).execute()
        except HttpError as exc:
            raise GoogleDriveError(
                f"Google Drive could not upload {source_path}: {exc}"
            ) from exc

    return await asyncio.to_thread(upload_file)


async def gdrive_delete(file_id: str) -> dict[str, object]:
    """Permanently delete a specific file from Google Drive."""
    def delete_file() -> None:
        try:
            service = _get_drive_service()
            service.files().delete(
                fileId=file_id,
                supportsAllDrives=True,
            ).execute()
        except HttpError as exc:
            raise GoogleDriveError(
                f"Google Drive could not delete file {file_id}: {exc}"
            ) from exc

    await asyncio.to_thread(delete_file)
    return {
        "deleted": True,
        "file_id": file_id,
    }


async def gdrive_list(folder_id: str) -> list[dict[str, object]]:
    """List files contained in a specific Google Drive folder."""
    def list_files() -> list[dict[str, object]]:
        try:
            service = _get_drive_service()
            result = service.files().list(
                q=f"'{folder_id}' in parents and trashed = false",
                fields=(
                    "files(id,name,mimeType,size,modifiedTime,webViewLink)"
                ),
                orderBy="name",
                pageSize=1000,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
            return result.get("files", [])
        except HttpError as exc:
            raise GoogleDriveError(
                f"Google Drive could not list folder {folder_id}: {exc}"
            ) from exc

    return await asyncio.to_thread(list_files)
