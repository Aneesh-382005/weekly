"""Command-line entry point: ``weekly``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .expand import expand
from .ics import to_ics
from .model import Schedule, ScheduleError

# Prefer a gitignored local file if the caller didn't pass -s and one exists.
_DEFAULT_CANDIDATES = ("schedule.local.yaml", "schedule.yaml")


def _default_schedule() -> str:
    for name in _DEFAULT_CANDIDATES:
        if Path(name).exists():
            return name
    return _DEFAULT_CANDIDATES[-1]


def _load(path: str) -> Schedule:
    try:
        return Schedule.from_yaml(path)
    except ScheduleError as exc:
        sys.exit(f"error: {exc}")


def _cmd_build(args) -> None:
    schedule = _load(args.schedule)
    out = Path(args.output)
    out.write_text(to_ics(schedule), newline="")
    occ = expand(schedule)
    print(
        f"wrote {out}  ({len(occ)} occurrences, "
        f"{len(schedule.events)} weekly events)"
    )


def _cmd_list(args) -> None:
    schedule = _load(args.schedule)
    occ = expand(schedule)
    if not occ:
        print("no occurrences in range")
        return
    for o in occ:
        print(
            f"{o.start:%a %Y-%m-%d}  "
            f"{o.start:%H:%M}-{o.end:%H:%M}  {schedule.event.title}"
        )
    print(f"\n{len(occ)} occurrences, {occ[0].date} to {occ[-1].date}")
    if schedule.exclusions:
        print("\nexcluded:")
        for x in schedule.exclusions:
            print(f"  {x.date:%a %Y-%m-%d}  {x.reason}")


def _cmd_gcal(args) -> None:
    from .gcal import sync

    schedule = _load(args.schedule)
    log = sync(
        schedule,
        calendar_name=args.calendar,
        client_secret=Path(args.client_secret),
        token_path=Path(args.token),
        dry_run=args.dry_run,
    )
    for line in log:
        print(line)
    print(
        f"\n{'would change' if args.dry_run else 'synced'} {len(log)} series "
        f"to calendar '{args.calendar}'"
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="weekly",
        description="Turn recurring weekly events described in YAML into an "
                    ".ics file (or sync them to Google Calendar).",
    )
    default = _default_schedule()
    p.add_argument(
        "-s", "--schedule", default=default,
        help=f"path to the schedule YAML (default: {default})",
    )
    sub = p.add_subparsers(dest="command", required=True)

    b = sub.add_parser("build", help="write an .ics file")
    b.add_argument("-o", "--output", default="calendar.ics", help="output path")
    b.set_defaults(func=_cmd_build)

    l = sub.add_parser("list", help="print every occurrence to the terminal")
    l.set_defaults(func=_cmd_list)

    g = sub.add_parser(
        "gcal", help="sync into a Google Calendar (needs [gcal] extra)"
    )
    g.add_argument("-c", "--calendar", default="weekly",
                   help="target calendar name (created if absent)")
    g.add_argument("--client-secret", default="client_secret.json",
                   help="OAuth desktop client JSON from Google Cloud Console")
    g.add_argument("--token", default=".gcal-token.json",
                   help="where to cache the OAuth token")
    g.add_argument("--dry-run", action="store_true",
                   help="show what would change without writing")
    g.set_defaults(func=_cmd_gcal)

    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
