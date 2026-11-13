"""Time and date helpers (ports of timediff, inctime, DisplayTime, ...)."""

from __future__ import annotations

import datetime as _dt
import re
from typing import Optional

DEFAULT_TIME_FORMAT = "%d:%02d:%02d"


def parse_hms(value: str) -> int:
    """Port of Tcl `scan $t "%d:%d:%d"`: lenient H:M[:S] to seconds.

    Non-numeric values (e.g. "pause") give 0, as in the original.
    """
    if not value:
        return 0
    m = re.match(r"\s*(-?\d+)(?::(\d+))?(?::(\d+))?", value)
    if not m:
        return 0
    h = int(m.group(1))
    mi = int(m.group(2) or 0)
    s = int(m.group(3) or 0)
    return h * 3600 + mi * 60 + s


def timediff(start: str, end: str) -> int:
    """Seconds from start to end (port of timediff)."""
    return parse_hms(end) - parse_hms(start)


def entry_duration(start: str, end: str) -> int:
    """Duration of a log entry in seconds.

    Unlike the original, a missing/invalid end time or an end before the
    start counts as zero rather than a negative duration.
    """
    if not start or not end:
        return 0
    d = timediff(start, end)
    return d if d > 0 else 0


def tcl_format(fmt: str, *args: int) -> str:
    """Apply a Tcl-style format such as "%d:%02d:%02d", ignoring extra args."""
    count = len(re.findall(r"%[-0-9.]*[a-zA-Z]", fmt.replace("%%", "")))
    try:
        return fmt % tuple(args[:count])
    except (TypeError, ValueError):
        return DEFAULT_TIME_FORMAT % tuple(args[:3])


def format_clock(secs: int, fmt: str = DEFAULT_TIME_FORMAT) -> str:
    """Format seconds as the original's inctime would (H:MM:SS by default)."""
    secs = int(secs)
    neg = secs < 0
    secs = abs(secs)
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    out = tcl_format(fmt, h, m, s)
    return "-" + out if neg else out


def now_time_str(fmt: str = DEFAULT_TIME_FORMAT, now: Optional[_dt.datetime] = None) -> str:
    now = now or _dt.datetime.now()
    return tcl_format(fmt, now.hour, now.minute, now.second)


def format_duration(secs: int, mode: str = "hhmm", hours_per_day: float = 7.58) -> str:
    """Port of DisplayTime.

    mode: 'hhmm' (showtime_format 0), 'hours' (1, decimal hours) or
    'days' (2, decimal days of `hours_per_day`).
    """
    secs = int(round(secs))
    if mode == "hours":
        return f"{secs / 3600.0:.2f}"
    if mode == "days":
        hpd = hours_per_day if hours_per_day and hours_per_day > 0 else 7.58
        return f"{secs / 3600.0 / hpd:.2f}"
    mins = int(round(secs / 60.0))
    return f"{mins // 60:02d}:{mins % 60:02d}"


_DATE_PATTERNS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d/%m/%Y",
]


def parse_datetime(value: str) -> Optional[_dt.datetime]:
    """Parse the date formats taglog stores (approximation of `clock scan`)."""
    if not value:
        return None
    v = value.strip()
    # Accept unpadded hours/minutes like "2026-11-12 9:5"
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?$", v)
    if m:
        try:
            return _dt.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                                int(m.group(4) or 0), int(m.group(5) or 0), int(m.group(6) or 0))
        except ValueError:
            return None
    for pat in _DATE_PATTERNS:
        try:
            return _dt.datetime.strptime(v, pat)
        except ValueError:
            continue
    return None


def parse_date(value: str) -> Optional[_dt.date]:
    d = parse_datetime(value)
    return d.date() if d else None


WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def weekday_name(d: _dt.date) -> str:
    """English weekday name as written by Tcl's clock format %A (C locale)."""
    return WEEKDAYS[d.weekday()]


def format_date(d: _dt.date, view_format: str = "YYYY-MM-DD") -> str:
    if view_format == "DD/MM/YYYY":
        return d.strftime("%d/%m/%Y")
    if view_format == "MM/DD/YYYY":
        return d.strftime("%m/%d/%Y")
    return d.isoformat()


def date_range(start: _dt.date, end: _dt.date):
    d = start
    while d <= end:
        yield d
        d += _dt.timedelta(days=1)


def parse_expected_time(value: str) -> Optional[int]:
    """Seconds for a project's Expected time, or None if it cannot be read.

    The original help describes it both as "hours" and as "hours and
    minutes", so accept: "40" (hours), "40.5" / "40,5" (decimal hours),
    "40:30" (h:mm) and "40:30:00" (h:mm:ss).
    """
    v = (value or "").strip()
    if not v:
        return None
    m = re.fullmatch(r"(\d+)(?:[.,](\d+))?", v)
    if m:
        return int(round(float(f"{m.group(1)}.{m.group(2) or 0}") * 3600))
    m = re.fullmatch(r"(\d+):([0-5]?\d)(?::([0-5]?\d))?", v)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3) or 0)
    return None
