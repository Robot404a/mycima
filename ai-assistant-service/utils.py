"""Small shared helpers (time, money, confirmation detection)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from config import settings

CINEMA_TZ = ZoneInfo(settings.cinema_timezone)

NEGATIVE_CONFIRMATION = re.compile(
    r"\b(no|nope|not|never|don'?t|do not|stop|cancel|non|annule|annuler|pas|jamais)\b",
    re.IGNORECASE,
)
POSITIVE_CONFIRMATION = re.compile(
    r"\b(yes|yeah|yep|ok|okay|sure|confirm|confirmed|hold|book|reserve|go ahead|do it|please|"
    r"oui|d'accord|confirme|réserve|reserve|vas-y|احجز|نعم)\b",
    re.IGNORECASE,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def money(value, currency: str = "MAD") -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):,.2f} {currency}"
    except (TypeError, ValueError):
        return f"{value} {currency}"


def explicit_confirmation(text: str) -> bool:
    if not text:
        return False
    if NEGATIVE_CONFIRMATION.search(text):
        return False
    return bool(POSITIVE_CONFIRMATION.search(text))


def local_datetime_parts(value: str | None) -> tuple[str, str]:
    """ISO 8601 (UTC) -> (local date 'YYYY-MM-DD', local time 'HH:MM') in the cinema timezone."""
    if not value:
        return "", ""
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return "", ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    local = parsed.astimezone(CINEMA_TZ)
    return local.strftime("%Y-%m-%d"), local.strftime("%H:%M")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
