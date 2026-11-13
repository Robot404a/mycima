"""Serialization helpers shared by the routers."""

from __future__ import annotations

from .models import Cinema, Hall, Movie, Showtime
from .timeutils import iso_utc


def row_label(index: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA."""
    label = ""
    index += 1
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        label = chr(65 + remainder) + label
    return label


def movie_out(movie: Movie) -> dict:
    return {
        "id": movie.id,
        "slug": movie.slug,
        "title": movie.title,
        "original_title": movie.original_title,
        "release_year": movie.release_year,
        "director": movie.director,
        "cast": list(movie.cast or []),
        "genres": list(movie.genres or []),
        "moods": list(movie.moods or []),
        "synopsis": movie.synopsis,
        "duration_minutes": movie.duration_minutes,
        "rating": movie.rating,
        "age_rating": movie.age_rating,
        "language": movie.language,
        "country": movie.country,
        "poster_url": movie.poster_url,
        "is_now_showing": movie.is_now_showing,
    }


def movie_brief(movie: Movie) -> dict:
    return {
        "id": movie.id,
        "slug": movie.slug,
        "title": movie.title,
        "release_year": movie.release_year,
        "duration_minutes": movie.duration_minutes,
        "genres": list(movie.genres or []),
        "poster_url": movie.poster_url,
    }


def cinema_out(cinema: Cinema) -> dict:
    return {
        "id": cinema.id,
        "name": cinema.name,
        "city": cinema.city,
        "address": cinema.address,
        "phone": cinema.phone,
    }


def cinema_brief(cinema: Cinema | None) -> dict | None:
    if cinema is None:
        return None
    return {"id": cinema.id, "name": cinema.name, "city": cinema.city}


def hall_out(hall: Hall) -> dict:
    return {
        "id": hall.id,
        "cinema_id": hall.cinema_id,
        "name": hall.name,
        "screen_type": hall.screen_type,
        "rows": hall.rows,
        "seats_per_row": hall.seats_per_row,
        "aisle_after": list(hall.aisle_after or []),
        "total_seats": hall.total_seats,
        "cinema": cinema_brief(hall.cinema),
    }


def hall_layout(hall: Hall) -> dict:
    """Seat layout consumed by the reservation service and the SVG seat map."""
    broken = set(hall.broken_seats or [])
    rows = []
    for row_index in range(hall.rows):
        label = row_label(row_index)
        seats = []
        for column in range(1, hall.seats_per_row + 1):
            seat_id = f"{label}{column}"
            seats.append({"id": seat_id, "number": column, "blocked": seat_id in broken})
        rows.append({"row": label, "seats": seats})
    return {
        "hall_id": hall.id,
        "name": hall.name,
        "screen_type": hall.screen_type,
        "rows": hall.rows,
        "seats_per_row": hall.seats_per_row,
        "aisle_after": list(hall.aisle_after or []),
        "row_labels": [row_label(index) for index in range(hall.rows)],
        "total_seats": hall.total_seats,
        "cinema": cinema_brief(hall.cinema),
        "layout": rows,
    }


def showtime_out(showtime: Showtime) -> dict:
    movie = showtime.movie
    hall = showtime.hall
    return {
        "id": showtime.id,
        "movie_id": showtime.movie_id,
        "hall_id": showtime.hall_id,
        "starts_at": iso_utc(showtime.starts_at),
        "price": round(showtime.price_cents / 100, 2),
        "price_cents": showtime.price_cents,
        "currency": showtime.currency,
        "language": showtime.language,
        "format": showtime.format,
        "movie": movie_brief(movie) if movie else None,
        "hall": {
            "id": hall.id,
            "name": hall.name,
            "screen_type": hall.screen_type,
            "total_seats": hall.total_seats,
        }
        if hall
        else None,
        "cinema": cinema_brief(hall.cinema if hall else None),
    }
