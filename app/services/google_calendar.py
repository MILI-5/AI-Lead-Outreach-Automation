
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

BASE_DIR = Path(__file__).resolve().parents[2]
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def get_calendar_service():
    """Authenticate and return the Google Calendar API service."""
    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError(
            f"Google OAuth credentials not found: {CREDENTIALS_FILE}"
        )

    credentials = None

    if TOKEN_FILE.exists():
        credentials = Credentials.from_authorized_user_file(
            str(TOKEN_FILE), SCOPES
        )

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())

    if not credentials or not credentials.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(CREDENTIALS_FILE), SCOPES
        )
        credentials = flow.run_local_server(port=0)

    TOKEN_FILE.write_text(credentials.to_json(), encoding="utf-8")

    return build("calendar", "v3", credentials=credentials)


def create_calendar_event(meeting):
    """Create a Google Calendar event for a booked meeting."""
    service = get_calendar_service()

    start_time = meeting.meeting_time.isoformat()

    from datetime import timedelta

    end_time = (
        meeting.meeting_time
        + timedelta(minutes=meeting.duration_minutes)
    ).isoformat()

    event = {
        "summary": meeting.meeting_title,
        "description": meeting.notes or "Lead discovery meeting",
        "start": {
            "dateTime": start_time,
            "timeZone": meeting.timezone,
        },
        "end": {
            "dateTime": end_time,
            "timeZone": meeting.timezone,
        },
    }

    if meeting.meeting_link:
        event["location"] = meeting.meeting_link

    created_event = (
        service.events()
        .insert(calendarId="primary", body=event)
        .execute()
    )

    return {
        "event_id": created_event["id"],
        "html_link": created_event.get("htmlLink"),
    }