"""Serialization helpers shared by the routers."""

from __future__ import annotations

from datetime import timezone

from .models import Cinema, Hall, Movie, Showtime
from .timeutils import iso_utc
from .timeutils import CINEMA_TZ


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
        "trailer_url": movie.trailer_url,
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


def hall_admin_out(hall: Hall) -> dict:
    """Shape used by the control room's halls & seats screen."""
    from .formats import hall_formats

    return {
        "id": hall.id,
        "cinema_id": hall.cinema_id,
        "name": hall.name,
        "screen_type": hall.screen_type,
        "row_count": hall.rows,
        "rows": hall.rows,
        "seats_per_row": hall.seats_per_row,
        "aisles_after": list(hall.aisle_after or []),
        "aisle_after": list(hall.aisle_after or []),
        "supported_formats": list(hall.supported_formats or []),
        "formats": hall_formats(hall),
        "description": hall.description,
        "is_active": bool(hall.is_active),
        "total_seats": hall.total_seats,
        "cinema": cinema_brief(hall.cinema),
    }


def movie_admin_out(movie: Movie) -> dict:
    """Shape used by the control room's catalogue screen."""
    return {
        **movie_out(movie),
        "tagline": movie.tagline,
        "duration_min": movie.duration_minutes,
        "release_date": movie.release_date.isoformat() if movie.release_date else None,
        "backdrop_url": movie.backdrop_url,
        "status": movie.status,
        "featured": bool(movie.featured),
        "mood_tags": list(movie.moods or []),
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


def showtime_admin_out(showtime: Showtime) -> dict:
    """Shape used by the control room's programme grid."""
    starts_at = showtime.starts_at
    local = starts_at.replace(tzinfo=timezone.utc).astimezone(CINEMA_TZ)
    return {
        "id": showtime.id,
        "movie_id": showtime.movie_id,
        "movie_title": showtime.movie.title if showtime.movie else "",
        "hall_id": showtime.hall_id,
        "starts_at": iso_utc(starts_at),
        "date": local.date().isoformat(),
        "time": local.strftime("%H:%M"),
        "format": showtime.format,
        "format_label": showtime.format,
        "format_value": {"2D": "STANDARD", "3D": "THREE_D", "IMAX": "IMAX"}.get(
            showtime.format, "STANDARD"
        ),
        "language": showtime.language,
        "base_price": round(showtime.price_cents / 100, 2),
        "price": round(showtime.price_cents / 100, 2),
        "price_cents": showtime.price_cents,
        "currency": showtime.currency,
        "is_active": bool(showtime.is_active),
        "hall": {"id": showtime.hall.id, "name": showtime.hall.name} if showtime.hall else None,
        "cinema": cinema_brief(showtime.hall.cinema if showtime.hall else None),
    }


def showtime_out(showtime: Showtime, with_seats: bool = False) -> dict:
    movie = showtime.movie
    hall = showtime.hall
    hall_payload = (
        {
            "id": hall.id,
            "name": hall.name,
            "screen_type": hall.screen_type,
            "rows": hall.rows,
            "seats_per_row": hall.seats_per_row,
            "aisle_after": list(hall.aisle_after or []),
            "total_seats": hall.total_seats,
        }
        if hall
        else None
    )
    if hall_payload is not None and with_seats:
        from .seats import seat_category_map

        hall_payload["seat_categories"] = seat_category_map(hall)
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
        "hall": hall_payload,
        "cinema": cinema_brief(hall.cinema if hall else None),
    }
