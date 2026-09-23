"""Send scheduled email notifications through Gmail."""

import base64
from email.message import EmailMessage
import os

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


GMAIL_RECIPIENT = "arushkumar091@gmail.com"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


class GmailError(RuntimeError):
    """Raised when an email cannot be sent through the Gmail API."""


def gmail_send_email(subject_line: str, body: str) -> dict[str, str]:
    """Send a plain-text email to the configured recipient using OAuth."""
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
            "Missing Gmail OAuth configuration: " + ", ".join(missing_secrets)
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
    message["To"] = GMAIL_RECIPIENT
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
        "recipient": GMAIL_RECIPIENT,
        "message_id": str(response.get("id", "")),
        "thread_id": str(response.get("threadId", "")),
    }
