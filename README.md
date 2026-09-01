# weekly

Describe a set of **weekly-recurring events** in a small YAML file; get a
standards-clean `.ics` you can import anywhere, or sync straight to Google
Calendar.

```yaml
range:
  name: "Spring 2026"
  start: 2026-01-12
  end: 2026-05-01
  timezone: "America/New_York"

event:
  title: "Intro to Pottery"
  location: "Community Center, Studio B"
  reminders_minutes: [60]

events:
  - { day: tue, start: "18:00", end: "20:00" }
  - { day: thu, start: "18:00", end: "20:00" }
  - { day: sat, start: "10:00", end: "13:00" }

exclude:
  - { date: 2026-01-19, reason: "MLK Day - center closed" }
```

```bash
pip install -e .           # only needs PyYAML
weekly list                # preview every occurrence
weekly build               # writes calendar.ics
```

## Why

Calendar apps and libraries make single events easy and *recurring events with
holiday gaps* annoying. Hand-writing iCalendar is fiddly: CRLF line endings,
75-octet line folding, `RRULE`/`EXDATE`, a `VTIMEZONE` block so times survive a
DST change. `weekly` takes a flat description of "this thing, these weekdays,
these times, this date window, minus these dates" and emits a file that
imports cleanly into Google Calendar, Apple Calendar, and Outlook, as **one
editable recurring series per weekday**, not dozens of loose events.

It's small (~500 lines, one runtime dependency) and the ICS writer is
stdlib-only, so it's also usable as a library or dropped into a script/agent
that needs to produce valid iCalendar without pulling a heavy package.

## Commands

| Command | Does |
|---|---|
| `weekly list` | Print every dated occurrence, plus the excluded dates and why. |
| `weekly build [-o FILE]` | Write an RFC 5545 `.ics` (default `calendar.ics`). |
| `weekly gcal [-c NAME]` | Create/update a recurring series in a Google Calendar. |

`-s / --schedule PATH` selects the input file. With no `-s`, `weekly` uses
`schedule.local.yaml` if present, else `schedule.yaml`.

`make build` / `make list` / `make test` are shortcuts.

## Keeping your real schedule private

The committed `schedule.yaml` is a **made-up example**. For your own events:

```bash
cp schedule.yaml schedule.local.yaml   # gitignored (*.local.yaml)
$EDITOR schedule.local.yaml
weekly build                           # picks up the .local file automatically
```

`schedule.local.yaml`, any `*.local.yaml`, every `*.ics`, and the Google OAuth
files are all in `.gitignore`, so a public clone of this repo shows only the
example.

## The schedule file

| Key | Meaning |
|---|---|
| `range.name` | Free label; appears in the calendar's display name. |
| `range.start` / `range.end` | Inclusive date window recurrence runs over. |
| `range.timezone` | Any IANA name (`America/New_York`, `Europe/London`, ...). |
| `event.title` | Event summary (same for every occurrence). |
| `event.location` | Optional location string. |
| `event.description` | Optional free text. |
| `event.reminders_minutes` | List of popup-alarm lead times; `[]` for none. |
| `events[]` | `{ day: mon..sun, start: "HH:MM", end: "HH:MM" }`. One per contiguous block; a day with a mid-event gap gets two entries. |
| `exclude[]` | `{ date: YYYY-MM-DD, reason: "..." }`. Any occurrence on that date is dropped; `reason` is a human note only. |

The loader is **strict**: a bad time (`25:00`), an end at or before its start,
a misspelled weekday, or `range.end` before `range.start` each produce a clear
message naming the offending key, not a traceback.

## How generic is it?

**Does not assume** anything about the *kind* of event (class, shift, meeting,
practice: all just strings), the timezone, the window length, which weekdays,
or that events are contiguous. It never parses a PDF or any source document;
you translate whatever your source looks like into the YAML.

**Is specialised in these ways:**

1. **One `event:` block for the whole file.** Every entry in `events:` shares
   the same title/location/description/reminders. Two genuinely different
   events need two YAML files (and two imports), or a small change to move
   those fields onto each `events[]` entry.
2. **Weekly recurrence only** (`RRULE:FREQ=WEEKLY`). No monthly/biweekly;
   biweekly would be a one-line `INTERVAL=2` addition.
3. **`exclude` is exact dates**, not ranges. List each date (or add a
   `skip_range`, it's a few lines).
4. **Embedded `VTIMEZONE` covers only US Eastern.** Other zones still emit
   `DTSTART;TZID=<zone>:...`, which every mainstream calendar app resolves from
   its own database; there's just no embedded fallback block for them.
5. **Timed single-day events only**: no all-day or multi-day events.
6. **Naive wall-clock times**: `14:00` means "2 pm local, whatever the offset
   that day", which is what a class meeting at a fixed clock time wants. DST
   transitions inside the range are handled by the `VTIMEZONE`.

## Google Calendar sync (optional)

```bash
pip install -e '.[gcal]'
# Desktop OAuth client from Google Cloud Console, saved as ./client_secret.json
weekly gcal --dry-run
weekly gcal -c "Intro to Pottery"
```

Each weekday's series is keyed by a deterministic `iCalUID` (from `range.name`
+ weekday + `event.title`), so re-running **updates** rather than duplicates.
`client_secret.json` and the cached token are gitignored.

## Layout

```
schedule.yaml         the committed example (made-up)
schedule.local.yaml   your real events (gitignored; you create this)
weekly/
  model.py            YAML to typed, validated Schedule       (~175 lines)
  expand.py           weekly events to dated occurrences        (~55 lines)
  ics.py              Schedule to .ics, stdlib only            (~150 lines)
  gcal.py             Schedule to Google Calendar (needs [gcal]) (~160 lines)
  cli.py              the `weekly` command                    (~120 lines)
tests/test_weekly.py  pytest, 14 checks
```

## Tests

```bash
make test
```

Covers range boundaries, exclusion, weekly cadence, ICS well-formedness (CRLF,
75-octet folding, `RRULE`/`EXDATE`, `DTSTART` never colliding with an
`EXDATE`), non-Eastern timezone handling, and loader validation.

## License

MIT
