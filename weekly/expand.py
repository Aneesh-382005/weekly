"""Expand recurring weekly events into concrete, dated occurrences."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from .model import Event, Schedule


@dataclass(frozen=True)
class Occurrence:
    """One dated instance of an event."""

    event: Event
    start: dt.datetime   # naive local wall-clock
    end: dt.datetime

    @property
    def date(self) -> dt.date:
        return self.start.date()


def _dates_for_weekday(start: dt.date, end: dt.date, weekday: int):
    """Yield every date in [start, end] falling on the given weekday (Mon=0)."""
    first = start + dt.timedelta(days=(weekday - start.weekday()) % 7)
    d = first
    while d <= end:
        yield d
        d += dt.timedelta(weeks=1)


def expand(schedule: Schedule) -> list[Occurrence]:
    """Every occurrence in range, chronologically, minus excluded dates."""
    excluded = schedule.excluded_dates
    out: list[Occurrence] = []
    for event in schedule.events:
        for d in _dates_for_weekday(
            schedule.range.start, schedule.range.end, event.weekday
        ):
            if d in excluded:
                continue
            out.append(Occurrence(
                event=event,
                start=dt.datetime.combine(d, event.start),
                end=dt.datetime.combine(d, event.end),
            ))
    out.sort(key=lambda o: o.start)
    return out
