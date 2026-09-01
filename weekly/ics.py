"""Render a :class:`Schedule` as an RFC 5545 iCalendar file.

One VEVENT per weekly event, using RRULE for the recurrence and EXDATE for the
excluded dates, so a calendar app shows a single editable series per weekday,
not dozens of loose events. A VTIMEZONE for America/New_York (with its DST
rules) is embedded so the wall-clock times survive the November clock change;
other zones fall back to the calendar app's own TZID database.
"""

from __future__ import annotations

import datetime as dt
import hashlib

from .expand import _dates_for_weekday
from .model import Schedule

_PRODID = "-//weekly//EN"
_ICS_WEEKDAY = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]


def _fold(line: str) -> str:
    """Fold lines longer than 75 octets, per RFC 5545 section 3.1."""
    out, raw = [], line.encode("utf-8")
    while len(raw) > 75:
        cut = 75
        while (raw[cut] & 0xC0) == 0x80:  # don't split a UTF-8 sequence
            cut -= 1
        out.append(raw[:cut].decode("utf-8"))
        raw = b" " + raw[cut:]
    out.append(raw.decode("utf-8"))
    return "\r\n".join(out)


def _esc(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _dt_local(value: dt.datetime, tzid: str) -> str:
    return f";TZID={tzid}:{value:%Y%m%dT%H%M%S}"


def _uid(schedule: Schedule, day: str) -> str:
    seed = f"{schedule.range.name}|{day}|{schedule.event.title}"
    digest = hashlib.sha1(seed.encode()).hexdigest()[:16]
    return f"{digest}@weekly"


# --- VTIMEZONE -----------------------------------------------------------
# Static block for US Eastern. Correct for any year from 2007 onward (the
# current DST rule: 2nd Sunday of March, 1st Sunday of November).
_VTIMEZONE_US_EASTERN = """BEGIN:VTIMEZONE
TZID:America/New_York
BEGIN:DAYLIGHT
TZOFFSETFROM:-0500
TZOFFSETTO:-0400
TZNAME:EDT
DTSTART:20070311T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:-0400
TZOFFSETTO:-0500
TZNAME:EST
DTSTART:20071104T020000
RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU
END:STANDARD
END:VTIMEZONE""".splitlines()


def to_ics(schedule: Schedule, *, now: dt.datetime | None = None) -> str:
    tz = schedule.range.timezone
    stamp = (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    ev = schedule.event

    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{_PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_esc(ev.title)} ({_esc(schedule.range.name)})",
    ]
    if tz == "America/New_York":
        lines += _VTIMEZONE_US_EASTERN

    for event in schedule.events:
        occ_dates = list(_dates_for_weekday(
            schedule.range.start, schedule.range.end, event.weekday
        ))
        if not occ_dates:
            continue
        # Anchor DTSTART on the first date the event actually happens, so the
        # series' first instance is never itself an EXDATE (some parsers balk).
        live_dates = [d for d in occ_dates if d not in schedule.excluded_dates]
        if not live_dates:
            continue
        first = live_dates[0]
        until = dt.datetime.combine(occ_dates[-1], event.end)
        dtstart = dt.datetime.combine(first, event.start)
        dtend = dt.datetime.combine(first, event.end)

        exdates = [
            dt.datetime.combine(d, event.start)
            for d in occ_dates
            if d in schedule.excluded_dates and d > first
        ]

        lines += [
            "BEGIN:VEVENT",
            f"UID:{_uid(schedule, event.day)}",
            f"DTSTAMP:{stamp}",
            f"SUMMARY:{_esc(ev.title)}",
            f"DTSTART{_dt_local(dtstart, tz)}",
            f"DTEND{_dt_local(dtend, tz)}",
            f"RRULE:FREQ=WEEKLY;BYDAY={_ICS_WEEKDAY[event.weekday]};"
            f"UNTIL={until:%Y%m%dT%H%M%S}",
        ]
        if exdates:
            joined = ",".join(f"{d:%Y%m%dT%H%M%S}" for d in exdates)
            lines.append(f"EXDATE;TZID={tz}:{joined}")
        if ev.location:
            lines.append(f"LOCATION:{_esc(ev.location)}")
        if ev.description:
            lines.append(f"DESCRIPTION:{_esc(ev.description)}")
        for minutes in ev.reminders_minutes:
            lines += [
                "BEGIN:VALARM",
                "ACTION:DISPLAY",
                f"DESCRIPTION:{_esc(ev.title)}",
                f"TRIGGER:-PT{minutes}M",
                "END:VALARM",
            ]
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(ln) for ln in lines) + "\r\n"
