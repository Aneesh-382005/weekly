"""Optional: sync the schedule into a Google Calendar.

This is an *extra*. The ICS path needs nothing installed; this one needs
``google-api-python-client`` and friends (``pip install '.[gcal]'``) plus an
OAuth client file. Run:

    weekly gcal --calendar "My Calendar"

Events are keyed by a deterministic ``iCalUID`` per (weekday, range), so
re-running updates the existing series instead of duplicating it.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from .expand import _dates_for_weekday
from .ics import _ICS_WEEKDAY, _uid
from .model import Schedule

_SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _load_credentials(client_secret: Path, token_path: Path):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:  # pragma: no cover - dependency hint
        raise SystemExit(
            "Google Calendar sync needs extra packages:\n"
            "    pip install 'weekly[gcal]'"
        ) from exc

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), _SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not client_secret.exists():
                raise SystemExit(
                    f"OAuth client file not found: {client_secret}\n"
                    "Create a Desktop OAuth client in Google Cloud Console and "
                    "save it there (or pass --client-secret)."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_secret), _SCOPES
            )
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())
    return creds


def _calendar_id(service, name: str) -> str:
    page_token = None
    while True:
        resp = service.calendarList().list(pageToken=page_token).execute()
        for cal in resp.get("items", []):
            if cal.get("summary") == name:
                return cal["id"]
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    created = service.calendars().insert(body={"summary": name}).execute()
    return created["id"]


def _event_body(schedule: Schedule, event, occ_dates: list[dt.date]) -> dict:
    tz = schedule.range.timezone
    ev = schedule.event
    live_dates = [d for d in occ_dates if d not in schedule.excluded_dates]
    first = live_dates[0]
    until = dt.datetime.combine(occ_dates[-1], event.end)
    exdates = [
        d for d in occ_dates if d in schedule.excluded_dates and d > first
    ]

    recurrence = [
        f"RRULE:FREQ=WEEKLY;BYDAY={_ICS_WEEKDAY[event.weekday]};"
        f"UNTIL={until:%Y%m%dT%H%M%S}"
    ]
    if exdates:
        joined = ",".join(
            f"{dt.datetime.combine(d, event.start):%Y%m%dT%H%M%S}"
            for d in exdates
        )
        recurrence.append(f"EXDATE;TZID={tz}:{joined}")

    return {
        "summary": ev.title,
        "location": ev.location or None,
        "description": ev.description or None,
        "iCalUID": _uid(schedule, event.day),
        "start": {
            "dateTime": dt.datetime.combine(first, event.start).isoformat(),
            "timeZone": tz,
        },
        "end": {
            "dateTime": dt.datetime.combine(first, event.end).isoformat(),
            "timeZone": tz,
        },
        "recurrence": recurrence,
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": m}
                for m in ev.reminders_minutes
            ],
        },
        "transparency": "opaque",
    }


def sync(
    schedule: Schedule,
    *,
    calendar_name: str,
    client_secret: Path,
    token_path: Path,
    dry_run: bool = False,
) -> list[str]:
    """Create or update one recurring event per weekly event. Returns a log."""
    from googleapiclient.discovery import build

    creds = _load_credentials(client_secret, token_path)
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    cal_id = _calendar_id(service, calendar_name)

    log: list[str] = []
    for event in schedule.events:
        occ_dates = list(_dates_for_weekday(
            schedule.range.start, schedule.range.end, event.weekday
        ))
        if not occ_dates or all(d in schedule.excluded_dates for d in occ_dates):
            continue
        body = _event_body(schedule, event, occ_dates)
        uid = body["iCalUID"]

        existing = service.events().list(
            calendarId=cal_id, iCalUID=uid, showDeleted=False,
        ).execute().get("items", [])

        label = f"{event.day} {event.start:%H:%M}-{event.end:%H:%M}"
        if dry_run:
            log.append(f"[dry-run] {'update' if existing else 'create'} {label}")
            continue

        if existing:
            service.events().update(
                calendarId=cal_id, eventId=existing[0]["id"], body=body,
            ).execute()
            log.append(f"updated {label}")
        else:
            service.events().insert(calendarId=cal_id, body=body).execute()
            log.append(f"created {label}")
    return log
