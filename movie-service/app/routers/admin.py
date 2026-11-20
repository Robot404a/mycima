"""Admin endpoints (JWT with role=admin, forwarded by the gateway).

The control room reads the catalogue, the programme, the venues and the seat
categories from here. Everything is an adapter over the same tables the public
endpoints use, so an admin edit is visible on the site immediately.
"""

from __future__ import annotations

from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..formats import default_supported_formats, format_for, normalize_format
from ..models import Cinema, Hall, Movie, Showtime
from ..schemas import (
    AdminHallPayload,
    AdminMoviePayload,
    AdminSeatPayload,
    AdminShowtimePayload,
    CinemaCreate,
    CinemaOut,
    HallOut,
    MovieOut,
    ShowtimeOut,
)
from ..seats import CATEGORIES, seat_category_map
from ..security import require_admin
from ..seed_data import PRICES_BY_SCREEN_TYPE, SHOWTIME_SLOTS
from ..serializers import (
    cinema_out,
    hall_admin_out,
    hall_out,
    movie_admin_out,
    movie_out,
    showtime_admin_out,
    showtime_out,
)
from ..timeutils import parse_cinema_datetime, utcnow
from ..utils import slugify

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

SCREEN_TYPES = {"standard", "premium", "imax", "vip"}


def _get_movie(db: Session, movie_id: int) -> Movie:
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found.")
    return movie


def _normalize_screen_type(value: str | None, default: str = "standard") -> str:
    screen = (value or default).strip().lower()
    if screen not in SCREEN_TYPES:
        raise HTTPException(
            status_code=422,
            detail="Screen type must be standard, premium, imax or vip.",
        )
    return screen


def _format_list(values: list[str] | None, screen_type: str) -> list[str]:
    if not values:
        return default_supported_formats(screen_type)
    return [normalize_format(item) for item in values]


def _admin_format_list(values: list[str] | None, screen_type: str) -> list[str]:
    """Store the admin vocabulary (STANDARD / THREE_D / IMAX) for the screens."""
    stored = _format_list(values, screen_type)
    return [{"2D": "STANDARD", "3D": "THREE_D", "IMAX": "IMAX"}.get(item, "STANDARD") for item in stored]


def _apply_movie_payload(movie: Movie, payload: AdminMoviePayload) -> None:
    data = payload.model_dump(exclude_unset=True)
    status_value = data.pop("status", None)
    flag = data.pop("is_now_showing", None)
    moods = data.pop("mood_tags", None)
    if moods is not None:
        data["moods"] = moods
    duration = data.pop("duration_min", None)
    if duration is not None and "duration_minutes" not in data:
        data["duration_minutes"] = duration
    poster_url = data.pop("poster_url", None)

    for key, value in data.items():
        if value is not None:
            setattr(movie, key, value)

    if poster_url:
        # The public poster path is stable; a custom URL becomes the source.
        if not poster_url.endswith(f"/posters/{movie.slug}.jpg"):
            movie.poster_path = poster_url

    if status_value is not None:
        movie.status = status_value
        movie.is_now_showing = status_value == "now_showing"
    elif flag is not None:
        movie.is_now_showing = bool(flag)
        movie.status = "now_showing" if flag else "coming_soon"

    if movie.release_date is not None:
        movie.release_year = movie.release_date.year


# ------------------------------------------------------------------ catalogue
@router.get("/movies", summary="Every film, including archived ones")
def list_admin_movies(
    q: str | None = Query(default=None, max_length=120),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(Movie)
    counter = select(func.count()).select_from(Movie)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(Movie.title.ilike(pattern))
        counter = counter.where(Movie.title.ilike(pattern))
    if status_filter:
        stmt = stmt.where(Movie.status == status_filter)
        counter = counter.where(Movie.status == status_filter)
    total = db.scalar(counter) or 0
    movies = db.scalars(stmt.order_by(Movie.title.asc()).limit(limit).offset(offset)).all()
    return {"items": [movie_admin_out(movie) for movie in movies], "total": total}


@router.post("/movies", status_code=status.HTTP_201_CREATED, summary="Add a movie")
def create_movie(payload: AdminMoviePayload, db: Session = Depends(get_db)) -> dict:
    if not payload.title:
        raise HTTPException(status_code=422, detail="A title is required.")
    slug = slugify(payload.slug or payload.title)
    if db.scalar(select(Movie.id).where(Movie.slug == slug)):
        raise HTTPException(status_code=409, detail=f"A movie with slug '{slug}' already exists.")
    year = payload.release_year or (payload.release_date.year if payload.release_date else date_type.today().year)
    movie = Movie(slug=slug, title=payload.title, release_year=year, synopsis="")
    _apply_movie_payload(movie, payload)
    movie.sync_keys()
    db.add(movie)
    db.commit()
    db.refresh(movie)
    return movie_admin_out(movie)


@router.patch("/movies/{movie_id}", summary="Update a movie")
def update_movie(movie_id: int, payload: AdminMoviePayload, db: Session = Depends(get_db)) -> dict:
    movie = _get_movie(db, movie_id)
    _apply_movie_payload(movie, payload)
    movie.sync_keys()
    db.commit()
    db.refresh(movie)
    return movie_admin_out(movie)


@router.delete("/movies/{movie_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a movie")
def delete_movie(movie_id: int, db: Session = Depends(get_db)) -> Response:
    movie = _get_movie(db, movie_id)
    db.delete(movie)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------ programme
def _slot_index(starts_at) -> int:
    for index, (hour, _minute) in enumerate(SHOWTIME_SLOTS):
        if starts_at.hour in {hour, hour + 1}:
            return index
    return 0


@router.get("/showtimes", summary="Every screening, past and future")
def list_admin_showtimes(
    date: date_type | None = None,
    movie_id: int | None = None,
    hall_id: int | None = None,
    is_active: bool | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    stmt = (
        select(Showtime)
        .options(joinedload(Showtime.movie), joinedload(Showtime.hall).joinedload(Hall.cinema))
        # Newest first, so a capped page always contains the live programme.
        .order_by(Showtime.starts_at.desc())
    )
    if date is not None:
        from ..timeutils import local_day_bounds

        start, end = local_day_bounds(date)
        stmt = stmt.where(Showtime.starts_at >= start, Showtime.starts_at < end)
    if movie_id is not None:
        stmt = stmt.where(Showtime.movie_id == movie_id)
    if hall_id is not None:
        stmt = stmt.where(Showtime.hall_id == hall_id)
    if is_active is not None:
        stmt = stmt.where(Showtime.is_active.is_(is_active))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    showtimes = list(reversed(db.scalars(stmt.limit(limit).offset(offset)).unique().all()))
    return {"items": [showtime_admin_out(showtime) for showtime in showtimes], "total": total}


def _showtime_values(
    payload: AdminShowtimePayload,
    movie: Movie | None = None,
    hall: Hall | None = None,
) -> dict:
    values: dict = {}
    if payload.starts_at is not None:
        values["starts_at"] = parse_cinema_datetime(payload.starts_at)
    if payload.language is not None:
        values["language"] = payload.language.strip() or "VO"
    if payload.price_cents is not None:
        values["price_cents"] = payload.price_cents
    elif payload.base_price is not None:
        values["price_cents"] = int(round(payload.base_price * 100))
    if payload.is_active is not None:
        values["is_active"] = bool(payload.is_active)
    if payload.format:
        values["format"] = normalize_format(payload.format)
        values["format_locked"] = True
    elif movie is not None and hall is not None and "starts_at" in values:
        values["format"] = format_for(movie, hall, _slot_index(values["starts_at"]))
    return values


@router.post("/showtimes", status_code=status.HTTP_201_CREATED, summary="Schedule a showtime")
def create_showtime(payload: AdminShowtimePayload, db: Session = Depends(get_db)) -> dict:
    if payload.movie_id is None or payload.hall_id is None or payload.starts_at is None:
        raise HTTPException(status_code=422, detail="Film, hall and start time are required.")
    movie = _get_movie(db, payload.movie_id)
    hall = db.get(Hall, payload.hall_id)
    if hall is None:
        raise HTTPException(status_code=404, detail="Hall not found.")

    values = _showtime_values(payload, movie, hall)
    starts_at = values["starts_at"]
    duplicate = db.scalar(
        select(Showtime.id).where(
            Showtime.movie_id == movie.id,
            Showtime.hall_id == hall.id,
            Showtime.starts_at == starts_at,
        )
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="This showtime already exists.")
    clash = db.scalar(
        select(Showtime.id).where(Showtime.hall_id == hall.id, Showtime.starts_at == starts_at)
    )
    if clash:
        raise HTTPException(status_code=409, detail="The hall is already busy at that time.")

    showtime = Showtime(
        movie_id=movie.id,
        hall_id=hall.id,
        starts_at=starts_at,
        price_cents=values.get("price_cents", PRICES_BY_SCREEN_TYPE.get(hall.screen_type, 5000)),
        language=values.get("language", "VO"),
        format=values.get("format") or normalize_format(None),
        format_locked=values.get("format_locked", False),
        is_active=values.get("is_active", True),
    )
    db.add(showtime)
    db.commit()
    showtime = db.scalar(
        select(Showtime)
        .options(joinedload(Showtime.hall).joinedload(Hall.cinema), joinedload(Showtime.movie))
        .where(Showtime.id == showtime.id)
    )
    return showtime_admin_out(showtime)


@router.patch("/showtimes/{showtime_id}", summary="Edit a screening")
def update_showtime(
    showtime_id: int, payload: AdminShowtimePayload, db: Session = Depends(get_db)
) -> dict:
    showtime = db.scalar(
        select(Showtime)
        .options(joinedload(Showtime.hall).joinedload(Hall.cinema), joinedload(Showtime.movie))
        .where(Showtime.id == showtime_id)
    )
    if showtime is None:
        raise HTTPException(status_code=404, detail="Showtime not found.")

    movie = _get_movie(db, payload.movie_id) if payload.movie_id else showtime.movie
    hall = db.get(Hall, payload.hall_id) if payload.hall_id else showtime.hall
    if hall is None:
        raise HTTPException(status_code=404, detail="Hall not found.")

    values = _showtime_values(payload, movie, hall)
    if payload.format is None and showtime.format_locked and "format" in values:
        # The admin already chose this screening's format; moving it in time
        # must not silently reset that choice.
        values.pop("format")
    starts_at = values.get("starts_at", showtime.starts_at)
    # Only a moved screening can clash; editing price/format/status never should.
    if hall.id != showtime.hall_id or starts_at != showtime.starts_at:
        clash = db.scalar(
            select(Showtime.id).where(
                Showtime.hall_id == hall.id,
                Showtime.starts_at == starts_at,
                Showtime.id != showtime.id,
            )
        )
        if clash:
            raise HTTPException(status_code=409, detail="The hall is already busy at that time.")

    showtime.movie_id = movie.id
    showtime.hall_id = hall.id
    for key, value in values.items():
        setattr(showtime, key, value)
    db.commit()
    db.refresh(showtime)
    return showtime_admin_out(showtime)


@router.delete("/showtimes/{showtime_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Publish/unpublish a screening")
def delete_showtime(showtime_id: int, db: Session = Depends(get_db)) -> Response:
    """Take a screening off the public programme without losing its bookings."""
    showtime = db.get(Showtime, showtime_id)
    if showtime is None:
        raise HTTPException(status_code=404, detail="Showtime not found.")
    showtime.is_active = False
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------ cinemas
@router.get("/cinemas", summary="Every cinema with its halls count")
def list_admin_cinemas(db: Session = Depends(get_db)) -> dict:
    cinemas = db.scalars(select(Cinema).order_by(Cinema.name.asc())).all()
    items = []
    for cinema in cinemas:
        payload = cinema_out(cinema)
        payload["description"] = cinema.description
        payload["amenities"] = list(cinema.amenities or [])
        payload["hall_count"] = db.scalar(
            select(func.count()).select_from(Hall).where(Hall.cinema_id == cinema.id)
        ) or 0
        items.append(payload)
    return {"items": items, "total": len(items)}


@router.post("/cinemas", response_model=CinemaOut, status_code=status.HTTP_201_CREATED, summary="Add a cinema")
def create_cinema(payload: CinemaCreate, db: Session = Depends(get_db)) -> dict:
    if db.scalar(select(Cinema.id).where(Cinema.name == payload.name)):
        raise HTTPException(status_code=409, detail="A cinema with that name already exists.")
    cinema = Cinema(**payload.model_dump())
    db.add(cinema)
    db.commit()
    db.refresh(cinema)
    return cinema_out(cinema)


# ------------------------------------------------------------------ halls & seats
@router.get("/halls", summary="Every hall with its formats and status")
def list_admin_halls(
    cinema_id: int | None = None,
    include_inactive: bool = True,
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(Hall).options(joinedload(Hall.cinema)).order_by(Hall.cinema_id.asc(), Hall.name.asc())
    if cinema_id is not None:
        stmt = stmt.where(Hall.cinema_id == cinema_id)
    if not include_inactive:
        stmt = stmt.where(Hall.is_active.is_(True))
    halls = db.scalars(stmt).unique().all()
    return {"items": [hall_admin_out(hall) for hall in halls], "total": len(halls)}


def _get_hall(db: Session, hall_id: int) -> Hall:
    hall = db.scalar(select(Hall).options(joinedload(Hall.cinema)).where(Hall.id == hall_id))
    if hall is None:
        raise HTTPException(status_code=404, detail="Hall not found.")
    return hall


@router.post("/halls", response_model=HallOut, status_code=status.HTTP_201_CREATED, summary="Add a hall")
def create_hall(payload: AdminHallPayload, db: Session = Depends(get_db)) -> dict:
    if payload.cinema_id is None or not payload.name:
        raise HTTPException(status_code=422, detail="Cinema and hall name are required.")
    cinema = db.get(Cinema, payload.cinema_id)
    if cinema is None:
        raise HTTPException(status_code=404, detail="Cinema not found.")
    duplicate = db.scalar(
        select(Hall.id).where(Hall.cinema_id == cinema.id, Hall.name == payload.name)
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="This cinema already has a hall with that name.")
    screen_type = _normalize_screen_type(payload.screen_type)
    hall = Hall(
        cinema_id=cinema.id,
        name=payload.name,
        screen_type=screen_type,
        rows=payload.rows or payload.row_count or 10,
        seats_per_row=payload.seats_per_row or 14,
        aisle_after=payload.aisle_after if payload.aisle_after is not None else (payload.aisles_after or []),
        broken_seats=payload.broken_seats or [],
        supported_formats=_admin_format_list(payload.supported_formats, screen_type),
        seat_categories={},
        description=payload.description,
        is_active=True if payload.is_active is None else bool(payload.is_active),
    )
    db.add(hall)
    db.commit()
    hall = db.scalar(select(Hall).options(joinedload(Hall.cinema)).where(Hall.id == hall.id))
    return hall_out(hall)


@router.patch("/halls/{hall_id}", summary="Edit a hall")
def update_hall(hall_id: int, payload: AdminHallPayload, db: Session = Depends(get_db)) -> dict:
    hall = _get_hall(db, hall_id)
    if payload.name is not None:
        hall.name = payload.name
    if payload.screen_type is not None:
        hall.screen_type = _normalize_screen_type(payload.screen_type)
    if payload.supported_formats is not None:
        hall.supported_formats = _admin_format_list(payload.supported_formats, hall.screen_type)
    if payload.description is not None:
        hall.description = payload.description
    if payload.is_active is not None:
        hall.is_active = bool(payload.is_active)
    db.commit()
    db.refresh(hall)
    return hall_admin_out(hall)


@router.delete("/halls/{hall_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a hall")
def delete_hall(hall_id: int, db: Session = Depends(get_db)) -> Response:
    hall = db.get(Hall, hall_id)
    if hall is None:
        raise HTTPException(status_code=404, detail="Hall not found.")
    db.delete(hall)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/halls/{hall_id}/layout", summary="Seat categories of a hall for the editor")
def admin_hall_layout(hall_id: int, db: Session = Depends(get_db)) -> dict:
    hall = _get_hall(db, hall_id)
    categories = seat_category_map(hall)
    broken = set(hall.broken_seats or [])
    seats = [
        {
            "seat_id": seat_id,
            "row_label": seat_id.rstrip("0123456789"),
            "seat_number": int(seat_id[len(seat_id.rstrip("0123456789")):]),
            "category": category,
            "blocked": seat_id in broken,
        }
        for seat_id, category in categories.items()
    ]
    return {
        "hall": {
            "id": hall.id,
            "name": hall.name,
            "row_count": hall.rows,
            "seats_per_row": hall.seats_per_row,
            "aisles_after": list(hall.aisle_after or []),
            "supported_formats": list(hall.supported_formats or []),
        },
        "cinema": {"id": hall.cinema.id, "name": hall.cinema.name} if hall.cinema else None,
        "seats": seats,
    }


@router.patch("/halls/{hall_id}/seats/{seat_id}", summary="Set the category of one seat")
def set_seat_category(
    hall_id: int, seat_id: str, payload: AdminSeatPayload, db: Session = Depends(get_db)
) -> dict:
    hall = _get_hall(db, hall_id)
    label = seat_id.strip().upper()
    if label not in seat_category_map(hall):
        raise HTTPException(status_code=404, detail="Seat not found in this hall.")
    if payload.category not in CATEGORIES:
        raise HTTPException(status_code=422, detail="Unknown seat category.")
    categories = dict(hall.seat_categories or {})
    categories[label] = payload.category
    hall.seat_categories = categories
    db.commit()
    return {"seat_id": label, "category": payload.category}
