import datetime as dt

import pytest

from weekly import Schedule, expand
from weekly.ics import to_ics
from weekly.model import ScheduleError

EXAMPLE = "schedule.yaml"


def _yaml(tmp_path, body: str):
    p = tmp_path / "s.yaml"
    p.write_text(body)
    return p


# --- the committed example -------------------------------------------------

@pytest.fixture(scope="module")
def example() -> Schedule:
    return Schedule.from_yaml(EXAMPLE)


def test_example_loads(example):
    assert example.range.name == "Spring 2026"
    assert len(example.events) == 3
    assert {e.day for e in example.events} == {"tue", "thu", "sat"}


def test_example_first_and_last(example):
    occ = expand(example)
    assert occ, "expected occurrences"
    # 2026-01-12 is a Monday; first event is Tuesday the 13th at 18:00.
    assert occ[0].start == dt.datetime(2026, 1, 13, 18, 0)
    assert occ[-1].date <= dt.date(2026, 5, 1)


def test_example_exclusions_removed(example):
    dates = {o.date for o in expand(example)}
    for x in example.excluded_dates:
        assert x not in dates
    assert dt.date(2026, 1, 19) not in dates       # MLK Day (a Monday, no event anyway)
    assert dt.date(2026, 3, 17) not in dates       # spring break Tuesday
    assert dt.date(2026, 3, 21) not in dates       # spring break Saturday


def test_no_occurrence_outside_range(example):
    for o in expand(example):
        assert example.range.start <= o.date <= example.range.end


def test_weekly_cadence(example):
    tuesdays = [o for o in expand(example) if o.date.weekday() == 1]
    gaps = {(b.date - a.date).days for a, b in zip(tuesdays, tuesdays[1:])}
    assert gaps <= {7, 14}  # 14 only where a Tuesday was excluded


# --- ICS output -----------------------------------------------------------

def test_ics_wellformed(example):
    text = to_ics(example, now=dt.datetime(2026, 1, 1))
    assert text.startswith("BEGIN:VCALENDAR\r\n")
    assert text.strip().endswith("END:VCALENDAR")
    assert text.count("BEGIN:VEVENT") == 3
    assert text.count("END:VEVENT") == 3
    assert "BEGIN:VTIMEZONE" in text          # example uses America/New_York
    assert "RRULE:FREQ=WEEKLY" in text
    # every line ends CRLF
    for line in text.split("\r\n")[:-1]:
        assert "\n" not in line


def test_ics_dtstart_never_equals_exdate(example):
    text = to_ics(example, now=dt.datetime(2026, 1, 1))
    for block in text.split("BEGIN:VEVENT")[1:]:
        starts = [ln for ln in block.splitlines() if ln.startswith("DTSTART")]
        exlines = [ln for ln in block.splitlines() if ln.startswith("EXDATE")]
        stamp = starts[0].split(":")[-1]
        for ex in exlines:
            assert stamp not in ex.split(":")[-1].split(",")


def test_ics_lines_folded_to_75_octets(example):
    text = to_ics(example, now=dt.datetime(2026, 1, 1))
    for line in text.split("\r\n"):
        assert len(line.encode("utf-8")) <= 75


def test_non_eastern_tz_still_emits_tzid(tmp_path):
    sched = Schedule.from_yaml(_yaml(tmp_path, """
range: {name: X, start: 2026-01-05, end: 2026-02-02, timezone: Europe/London}
event: {title: Standup}
events: [{day: mon, start: "09:30", end: "09:45"}]
"""))
    text = to_ics(sched, now=dt.datetime(2026, 1, 1))
    assert "DTSTART;TZID=Europe/London:" in text
    assert "BEGIN:VTIMEZONE" not in text  # only Eastern is embedded


# --- loader validation ----------------------------------------------------

def test_bad_time_rejected(tmp_path):
    with pytest.raises(ScheduleError):
        Schedule.from_yaml(_yaml(tmp_path, """
range: {name: X, start: 2026-09-02, end: 2026-12-11, timezone: America/New_York}
event: {title: T}
events: [{day: mon, start: "25:00", end: "26:00"}]
"""))


def test_end_before_start_rejected(tmp_path):
    with pytest.raises(ScheduleError):
        Schedule.from_yaml(_yaml(tmp_path, """
range: {name: X, start: 2026-09-02, end: 2026-12-11, timezone: America/New_York}
event: {title: T}
events: [{day: mon, start: "17:00", end: "14:00"}]
"""))


def test_range_end_before_start_rejected(tmp_path):
    with pytest.raises(ScheduleError):
        Schedule.from_yaml(_yaml(tmp_path, """
range: {name: X, start: 2026-12-11, end: 2026-09-02, timezone: America/New_York}
event: {title: T}
events: [{day: mon, start: "09:00", end: "10:00"}]
"""))


def test_unknown_weekday_rejected(tmp_path):
    with pytest.raises(ScheduleError):
        Schedule.from_yaml(_yaml(tmp_path, """
range: {name: X, start: 2026-09-02, end: 2026-12-11, timezone: America/New_York}
event: {title: T}
events: [{day: funday, start: "09:00", end: "10:00"}]
"""))


def test_missing_events_rejected(tmp_path):
    with pytest.raises(ScheduleError):
        Schedule.from_yaml(_yaml(tmp_path, """
range: {name: X, start: 2026-09-02, end: 2026-12-11, timezone: America/New_York}
event: {title: T}
"""))
