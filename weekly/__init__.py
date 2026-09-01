"""weekly: turn recurring weekly events described in YAML into an .ics file."""

from .model import Schedule, Event, EventInfo, Exclusion, RangeInfo
from .expand import Occurrence, expand
from .ics import to_ics

__all__ = [
    "Schedule", "Event", "EventInfo", "Exclusion", "RangeInfo",
    "Occurrence", "expand", "to_ics",
]
__version__ = "0.1.0"
