"""Time helpers.

Every datetime is stored as a *naive UTC* value so the same behaviour holds on
SQLite and PostgreSQL, and serialized with an explicit ``Z`` suffix.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .config import settings

CINEMA_TZ = ZoneInfo(settings.cinema_timezone)


def utcnow() -> datetime:
    """Current UTC time as a naive datetime (matches the storage format)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_utc_naive(value: datetime) -> datetime:
    """Normalize an aware datetime to naive UTC, and treat naive input as UTC."""
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def iso_utc(value: datetime) -> str:
    """Serialize a naive-UTC datetime as ISO 8601 with a ``Z`` suffix."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def local_day_bounds(day: date) -> tuple[datetime, datetime]:
    """UTC-naive [start, end) bounds of a calendar day in the cinema timezone."""
    start_local = datetime.combine(day, time.min, tzinfo=CINEMA_TZ)
    end_local = start_local + timedelta(days=1)
    return to_utc_naive(start_local), to_utc_naive(end_local)


def local_datetime(day: date, hour: int, minute: int = 0) -> datetime:
    """A cinema-local wall-clock time on ``day``, converted to naive UTC."""
    return to_utc_naive(datetime.combine(day, time(hour, minute), tzinfo=CINEMA_TZ))
