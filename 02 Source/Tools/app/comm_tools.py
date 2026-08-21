"""Tools for sending messages through communication channels."""

import base64
from email.message import EmailMessage
import os
from pathlib import Path

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


class GmailError(RuntimeError):
    """Raised when an email cannot be sent through the Gmail API."""


def gmail_send_email(
    recipient_list: list[str] | str,
    subject_line: str,
    body: str,
) -> dict[str, str]:
    """Send a plain-text email through Gmail using refresh-token OAuth."""
    if isinstance(recipient_list, str):
        recipients = [
            recipient.strip()
            for recipient in recipient_list.split(",")
            if recipient.strip()
        ]
    else:
        recipients = [
            str(recipient).strip()
            for recipient in recipient_list
            if str(recipient).strip()
        ]

    if not recipients:
        raise GmailError("At least one recipient email address is required.")
    if not subject_line.strip():
        raise GmailError("The email subject line is required.")
    if not body.strip():
        raise GmailError("The email body is required.")

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
        raise GmailError(
            "Missing Gmail OAuth configuration: "
            + ", ".join(missing_secrets)
        )

    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=GMAIL_SCOPES,
    )

    message = EmailMessage()
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject_line
    message.set_content(body)
    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

    try:
        gmail_service = build(
            "gmail",
            "v1",
            credentials=credentials,
            cache_discovery=False,
        )
        response = (
            gmail_service.users()
            .messages()
            .send(userId="me", body={"raw": encoded_message})
            .execute()
        )
    except (HttpError, OSError, ValueError) as exc:
        raise GmailError(f"Gmail API failed to send the email: {exc}") from exc

    return {
        "status": "sent",
        "message_id": str(response.get("id", "")),
        "thread_id": str(response.get("threadId", "")),
    }
