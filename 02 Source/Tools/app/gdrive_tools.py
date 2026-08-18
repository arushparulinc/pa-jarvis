import asyncio
from difflib import get_close_matches
from io import BytesIO
import os
from pathlib import Path
import threading

import asyncpg
from dotenv import load_dotenv
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

CREDENTIALS_FOLDER = PROJECT_ROOT / "credentials"
GDRIVE_CLIENT_SECRET_PATH = (
    CREDENTIALS_FOLDER / "gdrive_client_secret.json"
)
GDRIVE_TOKEN_PATH = CREDENTIALS_FOLDER / "gdrive_token.json"
GDRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
credentials_lock = threading.Lock()
FOLDER_MATCH_CUTOFF = 0.65


class GoogleDriveError(RuntimeError):
    """Raised when a Google Drive operation cannot be completed."""


def _get_root_folder_id() -> str:
    root_folder_id = os.getenv("GDRIVE_ROOT_FOLDER_ID", "").strip()
    if not root_folder_id:
        raise GoogleDriveError("GDRIVE_ROOT_FOLDER_ID is not configured.")
    return root_folder_id


async def _connect_postgres() -> asyncpg.Connection:
    try:
        return await asyncpg.connect(
            host=os.getenv("PGSQL_HOSTNAME"),
            port=int(os.getenv("PGSQL_PORT", "5432")),
            user=os.getenv("PGSQL_USER"),
            password=os.getenv("PGSQL_PASSWORD"),
            database=os.getenv("PGSQL_DBNAME"),
        )
    except Exception as exc:
        raise GoogleDriveError(
            f"Could not connect to PostgreSQL for Google Drive folders: {exc}"
        ) from exc


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


async def gdrive_get_folders() -> list[dict[str, object]]:
    """Refresh PostgreSQL with folders directly under the Drive root."""
    root_folder_id = _get_root_folder_id()

    def fetch_folders() -> list[dict[str, object]]:
        try:
            service = _get_drive_service()
            folders: list[dict[str, object]] = []
            page_token = None
            while True:
                result = service.files().list(
                    q=(
                        f"'{root_folder_id}' in parents and "
                        "mimeType = 'application/vnd.google-apps.folder' and "
                        "trashed = false"
                    ),
                    fields=(
                        "nextPageToken,"
                        "files(id,name,description,createdTime)"
                    ),
                    orderBy="name",
                    pageSize=1000,
                    pageToken=page_token,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                ).execute()
                folders.extend(result.get("files", []))
                page_token = result.get("nextPageToken")
                if not page_token:
                    break
            return folders
        except HttpError as exc:
            raise GoogleDriveError(
                f"Google Drive could not list root folders: {exc}"
            ) from exc

    folders = await asyncio.to_thread(fetch_folders)

    # Google Drive permits duplicate folder names, while the requested table
    # requires them to be unique. Keep the first folder for each exact name.
    unique_folders = {
        str(folder["name"]): folder
        for folder in reversed(folders)
        if folder.get("id") and folder.get("name")
    }
    synchronized_folders = list(unique_folders.values())

    connection = await _connect_postgres()
    try:
        async with connection.transaction():
            await connection.execute("DELETE FROM gdrive_folders")
            if synchronized_folders:
                await connection.executemany(
                    """
                    INSERT INTO gdrive_folders (
                        folder_id,
                        folder_name,
                        folder_description
                    )
                    VALUES ($1, $2, $3)
                    """,
                    [
                        (
                            str(folder["id"]),
                            str(folder["name"]),
                            (
                                str(folder["description"])
                                if folder.get("description") is not None
                                else None
                            ),
                        )
                        for folder in synchronized_folders
                    ],
                )
    except asyncpg.UndefinedTableError as exc:
        raise GoogleDriveError(
            "PostgreSQL table 'gdrive_folders' was not found."
        ) from exc
    finally:
        await connection.close()

    return synchronized_folders


async def _find_folder_id(folder_name: str) -> str | None:
    """Fuzzy-match a folder name against the PostgreSQL folder index."""
    connection = await _connect_postgres()
    try:
        rows = await connection.fetch(
            "SELECT folder_id, folder_name FROM gdrive_folders"
        )
    except asyncpg.UndefinedTableError as exc:
        raise GoogleDriveError(
            "PostgreSQL table 'gdrive_folders' was not found."
        ) from exc
    finally:
        await connection.close()

    requested_name = folder_name.strip().casefold()
    folder_ids = {
        str(row["folder_name"]).strip().casefold(): str(row["folder_id"])
        for row in rows
    }
    if requested_name in folder_ids:
        return folder_ids[requested_name]

    matches = get_close_matches(
        requested_name,
        folder_ids.keys(),
        n=1,
        cutoff=FOLDER_MATCH_CUTOFF,
    )
    return folder_ids[matches[0]] if matches else None


async def gdrive_list_folder(
    folder_name: str,
) -> list[dict[str, object]] | str:
    """Find a Drive folder by fuzzy name and list its contents."""
    folder_id = await _find_folder_id(folder_name)
    if folder_id is None:
        await gdrive_get_folders()
        folder_id = await _find_folder_id(folder_name)
    if folder_id is None:
        return "Folder Not Found in Gdrive"

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
