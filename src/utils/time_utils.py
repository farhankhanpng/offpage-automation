"""Timezone helpers.

All timestamps written to Sheets, reports and logs use India Standard Time,
regardless of the machine clock (GitHub runners run in UTC).
"""

from datetime import datetime, timedelta, timezone

try:  # zoneinfo is stdlib on 3.9+, but Windows needs the tzdata package for names
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except Exception:  # pragma: no cover - fallback when tz database is unavailable
    IST = timezone(timedelta(hours=5, minutes=30), name="IST")

TIMESTAMP_FMT = "%Y-%m-%d %H:%M:%S"


def now_ist() -> datetime:
    """Current time as an aware datetime in IST."""
    return datetime.now(IST)


def now_ist_str() -> str:
    """Current IST time formatted as 'YYYY-MM-DD HH:MM:SS'."""
    return now_ist().strftime(TIMESTAMP_FMT)


def today_ist_str() -> str:
    """Current IST date formatted as 'YYYY-MM-DD'."""
    return now_ist().strftime("%Y-%m-%d")


def parse_timestamp(value: str):
    """Parse a 'YYYY-MM-DD HH:MM:SS' (or 'YYYY-MM-DD') string as IST. Returns None if unparseable."""
    if not value:
        return None
    value = str(value).strip()
    for fmt in (TIMESTAMP_FMT, "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=IST)
        except ValueError:
            continue
    return None
