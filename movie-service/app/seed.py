"""Idempotent seed routine: cinemas, halls, real movies and showtimes."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import settings
from .models import Cinema, Hall, Movie, Showtime
from .seed_data import (
    CINEMAS,
    FORMAT_BY_SCREEN_TYPE,
    HALLS,
    MOVIES,
    PRICES_BY_SCREEN_TYPE,
    SHOWTIME_SLOTS,
)
from .timeutils import local_datetime, utcnow

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
                )
            )
    db.flush()
    return cinemas


def seed_movies(db: Session) -> int:
    existing = {slug for (slug,) in db.execute(select(Movie.slug))}
    created = 0
    for payload in MOVIES:
        if payload["slug"] in existing:
            continue
        movie = Movie(**payload)
        movie.sync_keys()
        db.add(movie)
        created += 1
    db.flush()
    return created


def seed_showtimes(db: Session) -> int:
    """Schedule every now-showing film on every hall for the next N days.

    For each day, each hall gets one slot per showtime time, so two films can
    never be scheduled in the same hall at the same hour.
    """
    movies = list(db.scalars(select(Movie).where(Movie.is_now_showing.is_(True)).order_by(Movie.id)))
    halls = list(db.scalars(select(Hall).order_by(Hall.id)))
    if not movies or not halls:
        return 0

    now = utcnow()
    created = 0
    cursor = 0
    for day_offset in range(settings.seed_days):
        day = date.today() + timedelta(days=day_offset)
        # Two passes per day so each film appears roughly twice.
        for _pass in range(2):
            for hour, minute in SHOWTIME_SLOTS:
                starts_at = local_datetime(day, hour, minute)
                if starts_at <= now:
                    continue
                for hall in halls:
                    movie = movies[cursor % len(movies)]
                    cursor += 1
                    exists = db.scalar(
                        select(Showtime.id).where(
                            Showtime.movie_id == movie.id,
                            Showtime.hall_id == hall.id,
                            Showtime.starts_at == starts_at,
                        )
                    )
                    if exists:
                        continue
                    db.add(
                        Showtime(
                            movie_id=movie.id,
                            hall_id=hall.id,
                            starts_at=starts_at,
                            price_cents=PRICES_BY_SCREEN_TYPE.get(hall.screen_type, 5000),
                            language="VF" if movie.language == "French" else "VO",
                            format=FORMAT_BY_SCREEN_TYPE.get(hall.screen_type, "2D"),
                        )
                    )
                    created += 1
        cursor += 5
    db.flush()
    return created


def seed_database(db: Session) -> None:
    cinemas = seed_cinemas_and_halls(db)
    movies_created = seed_movies(db)
    showtimes_created = 0
    if db.scalar(select(func.count(Showtime.id))) == 0:
        showtimes_created = seed_showtimes(db)
    db.commit()
    logger.info(
        "seed complete: %s cinemas, %s new movies, %s new showtimes",
        len(cinemas),
        movies_created,
        showtimes_created,
    )
