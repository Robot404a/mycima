"""Showtime / hall lookup.

The reservation service does not store halls or movies (the Movie service owns them).
All the assumptions about the Movie service live in THIS file, so when its real API is
known, only `_parse()` has to change.

http mode calls   GET {MOVIE_SERVICE_URL}/showtimes/{id}   and expects JSON like:
    {"price": 8.5, "starts_at": "2026-12-01T18:30:00Z",
     "hall": {"rows": 8, "seats_per_row": 12}}
"""
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import httpx
from fastapi import HTTPException

import config


def row_label(index: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA ..."""
    if index < 26:
        return chr(65 + index)
    return chr(64 + index // 26) + chr(65 + index % 26)


@dataclass(frozen=True)
class ShowtimeInfo:
    id: int
    price: Decimal
    rows: tuple[str, ...]
    seats_per_row: int
    starts_at: datetime | None = None

    def seat_labels(self) -> list[str]:
        return [f"{r}{n}" for r in self.rows for n in range(1, self.seats_per_row + 1)]

    def has_seat(self, label: str) -> bool:
        row = label.rstrip("0123456789")
        number = label[len(row):]
        return row in self.rows and number.isdigit() and 1 <= int(number) <= self.seats_per_row


_cache: dict[int, tuple[float, ShowtimeInfo]] = {}
_CACHE_SECONDS = 60


def get_showtime(showtime_id: int) -> ShowtimeInfo:
    if config.MOVIE_LOOKUP == "stub":
        return ShowtimeInfo(
            id=showtime_id,
            price=config.STUB_PRICE,
            rows=tuple(row_label(i) for i in range(config.STUB_ROWS)),
            seats_per_row=config.STUB_SEATS_PER_ROW,
        )

    cached = _cache.get(showtime_id)
    if cached and time.monotonic() - cached[0] < _CACHE_SECONDS:
        return cached[1]
    try:
        response = httpx.get(
            f"{config.MOVIE_SERVICE_URL}/showtimes/{showtime_id}", timeout=config.MOVIE_TIMEOUT_SECONDS
        )
    except httpx.HTTPError:
        raise HTTPException(503, "The movie service is temporarily unavailable.")
    if response.status_code == 404:
        raise HTTPException(404, "Showtime not found.")
    if response.status_code >= 400:
        raise HTTPException(502, "The movie service returned an error.")
    info = _parse(showtime_id, response.json())
    _cache[showtime_id] = (time.monotonic(), info)
    return info


def _parse(showtime_id: int, data: dict) -> ShowtimeInfo:
    """ADAPT THIS to the Movie service's real response."""
    hall = data.get("hall") or {}
    rows = hall.get("rows", data.get("rows"))
    per_row = hall.get("seats_per_row", hall.get("columns", data.get("seats_per_row")))
    raw_price = data.get("price", data.get("ticket_price"))
    try:
        if not (isinstance(rows, int) and isinstance(per_row, int) and rows > 0 and per_row > 0):
            raise ValueError("hall layout")
        price = Decimal(str(raw_price))
    except (ValueError, InvalidOperation):
        raise HTTPException(502, "The movie service returned an unexpected showtime format.")

    starts_at = None
    raw_start = data.get("starts_at", data.get("start_time"))
    if raw_start:
        try:
            starts_at = datetime.fromisoformat(str(raw_start).replace("Z", "+00:00"))
            if starts_at.tzinfo is None:
                starts_at = starts_at.replace(tzinfo=timezone.utc)
        except ValueError:
            starts_at = None
    return ShowtimeInfo(
        id=showtime_id, price=price, rows=tuple(row_label(i) for i in range(rows)),
        seats_per_row=per_row, starts_at=starts_at,
    )
