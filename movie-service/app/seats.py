"""Seat categories for a hall.

A hall always has a default VIP band (two rows around two-thirds back — the
"middle / back-middle" sweet spot most cinemas use), and the admin can repaint
any individual seat. The effective category of every seat is returned to the
reservation service, so the price it charges always matches the seat map.
"""

from __future__ import annotations

from .models import Hall
from .serializers import row_label

CATEGORIES = ("REGULAR", "VIP", "VVIP")

# Share of the hall that sits in front of the default VIP band.
VIP_BAND_START_RATIO = 0.6
VIP_BAND_ROWS = 2


def default_category(rows: int, row_index: int) -> str:
    if rows <= 0:
        return "REGULAR"
    start = min(int(rows * VIP_BAND_START_RATIO), max(0, rows - VIP_BAND_ROWS))
    return "VIP" if start <= row_index < start + VIP_BAND_ROWS else "REGULAR"


def seat_category_map(hall: Hall) -> dict[str, str]:
    """Every seat of the hall mapped to its effective category."""
    overrides = {
        str(seat_id).upper(): str(category).upper()
        for seat_id, category in (hall.seat_categories or {}).items()
        if str(category).upper() in CATEGORIES
    }
    categories: dict[str, str] = {}
    for row_index in range(hall.rows):
        row = row_label(row_index)
        fallback = default_category(hall.rows, row_index)
        for number in range(1, hall.seats_per_row + 1):
            seat_id = f"{row}{number}"
            categories[seat_id] = overrides.get(seat_id, fallback)
    return categories


def category_counts(categories: dict[str, str]) -> dict[str, int]:
    counts = {category: 0 for category in CATEGORIES}
    for category in categories.values():
        counts[category] = counts.get(category, 0) + 1
    return counts
