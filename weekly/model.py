"""Typed representation of the schedule YAML plus its loader.

The YAML is deliberately forgiving to write; this module is where it becomes
strict. Every mistake a human could plausibly make in the file is turned into
a clear message here rather than a stack trace later.

Vocabulary
----------
range       the date window recurrence runs over (start/end/timezone)
event       one weekly recurring block: a weekday + start/end time
exclude     a date on which no occurrence is generated
occurrence  one concrete dated instance of an event (see expand.py)
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_WEEKDAYS = {
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
}


class ScheduleError(ValueError):
    """Raised when the schedule YAML is malformed."""


def _require(mapping: dict, key: str, where: str):
    if not isinstance(mapping, dict) or key not in mapping:
        raise ScheduleError(f"{where}: missing required key '{key}'")
    return mapping[key]


def _parse_date(value, where: str) -> dt.date:
    if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        return value
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError:
        raise ScheduleError(f"{where}: '{value}' is not a YYYY-MM-DD date")


def _parse_time(value, where: str) -> dt.time:
    try:
        hh, mm = str(value).strip().split(":")
        return dt.time(int(hh), int(mm))
    except (ValueError, TypeError):
        raise ScheduleError(f"{where}: '{value}' is not a HH:MM time")


@dataclass(frozen=True)
class RangeInfo:
    """The date window recurrence runs over."""

    name: str
    start: dt.date
    end: dt.date
    timezone: str

    def __post_init__(self):
        if self.end < self.start:
            raise ScheduleError(
                f"range: end ({self.end}) is before start ({self.start})"
            )


@dataclass(frozen=True)
class EventInfo:
    """The shared description applied to every occurrence."""

    title: str
    location: str
    description: str
    reminders_minutes: tuple[int, ...]


@dataclass(frozen=True)
class Event:
    """One weekly recurring block: a weekday and a start/end time."""

    day: str          # canonical lowercase, e.g. "mon"
    start: dt.time
    end: dt.time

    @property
    def weekday(self) -> int:
        return _WEEKDAYS[self.day]

    def __post_init__(self):
        if self.end <= self.start:
            raise ScheduleError(
                f"events {self.day}: end ({self.end}) must be after start "
                f"({self.start})"
            )


@dataclass(frozen=True)
class Exclusion:
    date: dt.date
    reason: str


@dataclass(frozen=True)
class Schedule:
    range: RangeInfo
    event: EventInfo
    events: tuple[Event, ...]
    exclusions: tuple[Exclusion, ...]
    source: Path | None = field(default=None, compare=False)

    @property
    def excluded_dates(self) -> frozenset[dt.date]:
        return frozenset(e.date for e in self.exclusions)

    # --- loading ----------------------------------------------------------

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Schedule":
        path = Path(path)
        if not path.exists():
            raise ScheduleError(f"schedule file not found: {path}")
        raw = yaml.safe_load(path.read_text()) or {}
        if not isinstance(raw, dict):
            raise ScheduleError(f"{path}: top level must be a mapping")

        range_raw = _require(raw, "range", str(path))
        date_range = RangeInfo(
            name=str(_require(range_raw, "name", "range")),
            start=_parse_date(_require(range_raw, "start", "range"), "range.start"),
            end=_parse_date(_require(range_raw, "end", "range"), "range.end"),
            timezone=str(_require(range_raw, "timezone", "range")),
        )

        event_raw = _require(raw, "event", str(path))
        reminders = event_raw.get("reminders_minutes", []) or []
        if not all(isinstance(m, int) and m >= 0 for m in reminders):
            raise ScheduleError(
                "event.reminders_minutes: must be non-negative integers"
            )
        event = EventInfo(
            title=str(_require(event_raw, "title", "event")),
            location=str(event_raw.get("location", "")),
            description=str(event_raw.get("description", "")),
            reminders_minutes=tuple(reminders),
        )

        events_raw = _require(raw, "events", str(path))
        if not events_raw:
            raise ScheduleError("events: at least one entry is required")
        events = []
        for i, e in enumerate(events_raw):
            where = f"events[{i}]"
            day = str(_require(e, "day", where)).strip().lower()[:3]
            if day not in _WEEKDAYS:
                raise ScheduleError(
                    f"{where}: '{e.get('day')}' is not a weekday (mon..sun)"
                )
            events.append(Event(
                day=day,
                start=_parse_time(_require(e, "start", where), f"{where}.start"),
                end=_parse_time(_require(e, "end", where), f"{where}.end"),
            ))

        exclusions = []
        for i, x in enumerate(raw.get("exclude", []) or []):
            where = f"exclude[{i}]"
            exclusions.append(Exclusion(
                date=_parse_date(_require(x, "date", where), f"{where}.date"),
                reason=str(x.get("reason", "")),
            ))

        return cls(
            range=date_range,
            event=event,
            events=tuple(events),
            exclusions=tuple(sorted(exclusions, key=lambda x: x.date)),
            source=path,
        )
