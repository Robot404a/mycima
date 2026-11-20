"""Idempotent seed routine: cinemas, halls, real movies and showtimes."""

from __future__ import annotations

import logging
from datetime import date, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload

from .config import settings
from .formats import default_supported_formats, format_for
from .models import Cinema, Hall, Movie, Showtime
from .seed_data import (
    CINEMAS,
    HALLS,
    MOVIES,
    PRICES_BY_SCREEN_TYPE,
    SHOWTIME_SLOTS,
)
from .timeutils import CINEMA_TZ, local_datetime, utcnow

logger = logging.getLogger("movie-service.seed")


def seed_cinemas_and_halls(db: Session) -> dict[str, Cinema]:
    cinemas: dict[str, Cinema] = {}
    for payload in CINEMAS:
        cinema = db.scalar(select(Cinema).where(Cinema.name == payload["name"]))
        if cinema is None:
            cinema = Cinema(**payload)
            db.add(cinema)
            db.flush()
        cinemas[cinema.name] = cinema

    for payload in HALLS:
        cinema = cinemas[payload["cinema"]]
        hall = db.scalar(select(Hall).where(Hall.cinema_id == cinema.id, Hall.name == payload["name"]))
        if hall is None:
            db.add(
                Hall(
                    cinema_id=cinema.id,
                    name=payload["name"],
                    screen_type=payload["screen_type"],
                    rows=payload["rows"],
                    seats_per_row=payload["seats_per_row"],
                    aisle_after=payload["aisle_after"],
                    broken_seats=payload["broken_seats"],
                    supported_formats=default_supported_formats(payload["screen_type"]),
                    seat_categories={},
                )
            )
    db.flush()
    return cinemas


def seed_movies(db: Session) -> int:
    existing = {slug for (slug,) in db.execute(select(Movie.slug))}
    created = 0
    for payload in MOVIES:
        if payload["slug"] in existing:
            # Backfill covers added after the row was first seeded.
            movie = db.scalar(select(Movie).where(Movie.slug == payload["slug"]))
            if movie is not None and not movie.poster_path and payload.get("poster_path"):
                movie.poster_path = payload["poster_path"]
            continue
        movie = Movie(**payload)
        movie.sync_keys()
        db.add(movie)
        created += 1
    db.flush()
    return created


def seed_showtimes(db: Session) -> int:
    """Top up the programme so every now-showing film has daily screenings.

    Each hall gets one film per time slot per day, assigned round-robin so the
    whole catalog is covered every day. The routine is idempotent and additive:
    it runs on every startup (and on a timer) to keep the rolling window full
    instead of only seeding once on an empty database.
    """
    movies = list(db.scalars(select(Movie).where(Movie.is_now_showing.is_(True)).order_by(Movie.id)))
    halls = list(db.scalars(select(Hall).order_by(Hall.id)))
    if not movies or not halls:
        return 0

    now = utcnow()
    created = 0
    for day_offset in range(settings.seed_days):
        day = date.today() + timedelta(days=day_offset)
        for slot_index, (hour, minute) in enumerate(SHOWTIME_SLOTS):
            starts_at = local_datetime(day, hour, minute)
            if starts_at <= now:
                continue
            for hall_index, hall in enumerate(halls):
                # Rotate the starting film per day and slot so the whole catalog
                # is on screen every day and no hall is double-booked.
                movie = movies[(day.toordinal() + slot_index * len(halls) + hall_index) % len(movies)]
                occupied = db.scalar(
                    select(Showtime.id).where(
                        Showtime.hall_id == hall.id,
                        Showtime.starts_at == starts_at,
                    )
                )
                if occupied:
                    continue
                show_format = format_for(movie, hall, slot_index)
                db.add(
                    Showtime(
                        movie_id=movie.id,
                        hall_id=hall.id,
                        starts_at=starts_at,
                        price_cents=PRICES_BY_SCREEN_TYPE.get(hall.screen_type, 5000),
                        language="VF" if movie.language == "French" else "VO",
                        format=show_format,
                    )
                )
                created += 1

    apply_format_rules(db)
    db.flush()
    return created


def apply_format_rules(db: Session) -> int:
    """Re-align auto-assigned formats with the film/room rule.

    Screenings an admin edited carry ``format_locked`` and are left alone, so a
    deliberate choice in the control room is never overwritten by a top-up.
    """
    rows = (
        db.scalars(
            select(Showtime)
            .options(joinedload(Showtime.movie), joinedload(Showtime.hall))
            .where(Showtime.starts_at >= utcnow(), Showtime.format_locked.is_(False))
        )
        .unique()
        .all()
    )
    changed = 0
    for showtime in rows:
        if showtime.movie is None or showtime.hall is None:
            continue
        local_hour = showtime.starts_at.replace(tzinfo=timezone.utc).astimezone(CINEMA_TZ).hour
        slot_index = next(
            (index for index, (hour, _minute) in enumerate(SHOWTIME_SLOTS) if hour == local_hour),
            0,
        )
        desired = format_for(showtime.movie, showtime.hall, slot_index)
        if showtime.format != desired:
            showtime.format = desired
            changed += 1
    if changed:
        logger.info("format rule realigned %s screenings", changed)
    return changed


def seed_database(db: Session) -> None:
    cinemas = seed_cinemas_and_halls(db)
    movies_created = seed_movies(db)
    showtimes_created = seed_showtimes(db)
    db.commit()
    logger.info(
        "seed complete: %s cinemas, %s new movies, %s new showtimes",
        len(cinemas),
        movies_created,
        showtimes_created,
    )
