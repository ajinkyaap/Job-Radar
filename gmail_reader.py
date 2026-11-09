"""Read-only Gmail OAuth helper for short-lived application verification codes."""

import base64
import re
from pathlib import Path

from bs4 import BeautifulSoup

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CLIENT_FILE = "gmail_client_secret.json"
TOKEN_FILE = "gmail_token.json"


def get_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    credentials = None
    if Path(TOKEN_FILE).is_file():
        credentials = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            if not Path(CLIENT_FILE).is_file():
                raise FileNotFoundError(f"Missing {CLIENT_FILE}")
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_FILE, SCOPES)
            credentials = flow.run_local_server(port=0)
        Path(TOKEN_FILE).write_text(credentials.to_json(), encoding="utf-8")
    return build("gmail", "v1", credentials=credentials)


def _decode_part(part: dict) -> str:
    data = (part.get("body") or {}).get("data")
    if data:
        return base64.urlsafe_b64decode(data + "===").decode("utf-8", errors="ignore")
    return "".join(_decode_part(child) for child in part.get("parts", []))


def extract_verification_code(text: str) -> str | None:
    """Extract Greenhouse's six digits, including separator-formatted codes."""
    code_context = re.search(
        r"copy and paste this code.*?(?:field|application)[:\s#]*([\d\s*\-_.]{6,32})",
        text,
        re.I | re.S,
    )
    if code_context:
        digits = "".join(re.findall(r"\d", code_context.group(1)))
        if len(digits) >= 6:
            return digits[:6]
    match = re.search(r"\b(\d{6})\b", text)
    return match.group(1) if match else None


def get_latest_verification_code(max_age_minutes: int = 60) -> str | None:
    service = get_service()
    query = (
        'from:(no-reply@us.greenhouse-mail.io) '
        'subject:("Security code for your application") '
        f'newer_than:{max_age_minutes}m'
    )
    response = service.users().messages().list(userId="me", q=query, maxResults=10).execute()
    for message in response.get("messages", []):
        full = service.users().messages().get(userId="me", id=message["id"], format="full").execute()
        text = _decode_part(full.get("payload", {}))
        text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
        code = extract_verification_code(text)
        if code:
            return code
    return None


if __name__ == "__main__":
    get_service()
    print(f"Gmail OAuth token ready: {TOKEN_FILE}")
