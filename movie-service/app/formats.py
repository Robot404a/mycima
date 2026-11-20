"""Screening formats and the rule that decides them.

The format of a screening is a property of the film and the room, not a random
pick:

* a hall only offers the formats it is equipped for (`supported_formats`);
* a 3D-capable hall plays its afternoon slot in 3D, whatever the film's age;
* recent releases (within `PREMIUM_RELEASE_WINDOW_YEARS`) may also use the
  other premium format of that hall — IMAX in an IMAX room;
* older films, and any film in a plain room without 3D, play in 2D.

The seeder applies the rule, and an admin edit locks the format so later
top-ups never overwrite it.
"""

from __future__ import annotations

from datetime import date

from .models import Hall, Movie

PREMIUM_RELEASE_WINDOW_YEARS = 3

# Admin vocabulary -> the value stored on a showtime.
FORMAT_ALIASES = {
    "STANDARD": "2D",
    "2D": "2D",
    "THREE_D": "3D",
    "3D": "3D",
    "IMAX": "IMAX",
    "VIP": "VIP",
}

# The reverse, used by the admin programme grid.
ADMIN_FORMAT_VALUES = {"2D": "STANDARD", "3D": "THREE_D", "IMAX": "IMAX", "VIP": "STANDARD"}


def normalize_format(value: str | None, default: str = "2D") -> str:
    if not value:
        return default
    return FORMAT_ALIASES.get(str(value).strip().upper(), default)


def default_supported_formats(screen_type: str) -> list[str]:
    screen = (screen_type or "standard").strip().lower()
    if screen == "imax":
        return ["IMAX", "STANDARD"]
    if screen == "premium":
        return ["STANDARD", "THREE_D"]
    return ["STANDARD"]


def hall_formats(hall: Hall) -> list[str]:
    formats = [normalize_format(item) for item in (hall.supported_formats or [])]
    return formats or [normalize_format(item) for item in default_supported_formats(hall.screen_type)]


def is_premium_release(movie: Movie, today: date | None = None) -> bool:
    reference = today or date.today()
    return movie.release_year >= reference.year - PREMIUM_RELEASE_WINDOW_YEARS


def format_for(movie: Movie, hall: Hall, slot_index: int, today: date | None = None) -> str:
    """The format a screening should carry, given the film, the room and the slot."""
    supported = hall_formats(hall)
    # 3D comes from the room's equipment, not from how new the film is. Gating it
    # on release year left 3D almost absent from the programme entirely.
    if "3D" in supported and slot_index == 1:
        return "3D"
    if not is_premium_release(movie, today):
        return "2D"
    if hall.screen_type == "imax" and "IMAX" in supported:
        return "IMAX"
    return "2D"
