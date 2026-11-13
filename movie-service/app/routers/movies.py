"""Catalog endpoints: list/search movies, movie details, movie showtimes."""

from __future__ import annotations

from datetime import date as date_type
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Hall, Movie, Showtime
from ..schemas import MovieListOut, MovieOut, ShowtimeListOut
from ..serializers import movie_out, showtime_out
from ..timeutils import local_day_bounds, utcnow

router = APIRouter(prefix="/movies", tags=["movies"])


def _tag_filter(column, tag: str):
    return column.like(f"%|{tag.strip().lower()}|%")


@router.get("/genres", response_model=list[str], summary="Distinct genres in the catalog")
def list_genres(db: Session = Depends(get_db)) -> list[str]:
    genres: set[str] = set()
    for (value,) in db.execute(select(Movie.genres)):
        genres.update(value or [])
    return sorted(genres)


@router.get("/moods", response_model=list[str], summary="Distinct mood tags used by the AI assistant")
def list_moods(db: Session = Depends(get_db)) -> list[str]:
    moods: set[str] = set()
    for (value,) in db.execute(select(Movie.moods)):
        moods.update(value or [])
    return sorted(moods)


@router.get("", response_model=MovieListOut, summary="List and search movies")
def list_movies(
    genre: str | None = Query(default=None, description="Filter by genre, e.g. Animation"),
    mood: str | None = Query(default=None, description="Filter by mood tag, e.g. romantic"),
    date: date_type | None = Query(default=None, description="Only movies with a showtime that day"),
    cinema_id: int | None = Query(default=None, description="Only movies shown in this cinema"),
    q: str | None = Query(default=None, description="Search in title, original title and director"),
    now_showing: bool | None = Query(default=None),
    sort: Literal["rating", "title", "year", "newest"] = "rating",
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(Movie)

    if genre:
        stmt = stmt.where(_tag_filter(Movie.genres_key, genre))
    if mood:
        stmt = stmt.where(_tag_filter(Movie.moods_key, mood))
    if now_showing is not None:
        stmt = stmt.where(Movie.is_now_showing.is_(now_showing))

    if q:
        needle = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Movie.title.ilike(needle),
                Movie.original_title.ilike(needle),
                Movie.director.ilike(needle),
            )
        )

    if date is not None or cinema_id is not None:
        bookable = select(Showtime.movie_id)
        if cinema_id is not None:
            bookable = bookable.join(Hall, Showtime.hall_id == Hall.id).where(Hall.cinema_id == cinema_id)
        if date is not None:
            start, end = local_day_bounds(date)
            bookable = bookable.where(Showtime.starts_at >= start, Showtime.starts_at < end)
        else:
            bookable = bookable.where(Showtime.starts_at >= utcnow())
        stmt = stmt.where(Movie.id.in_(bookable))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    order = {
        "rating": Movie.rating.desc(),
        "title": Movie.title.asc(),
        "year": Movie.release_year.desc(),
        "newest": Movie.created_at.desc(),
    }[sort]
    items = db.scalars(stmt.order_by(order, Movie.id.asc()).limit(limit).offset(offset)).all()
    return {
        "items": [movie_out(movie) for movie in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def resolve_movie(db: Session, movie_ref: str) -> Movie:
    movie = None
    if movie_ref.isdigit():
        movie = db.get(Movie, int(movie_ref))
    if movie is None:
        movie = db.scalar(select(Movie).where(Movie.slug == movie_ref.strip().lower()))
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found.")
    return movie


@router.get("/{movie_ref}", response_model=MovieOut, summary="Movie details by id or slug")
def get_movie(movie_ref: str, db: Session = Depends(get_db)) -> dict:
    return movie_out(resolve_movie(db, movie_ref))


@router.get("/{movie_ref}/showtimes", response_model=ShowtimeListOut, summary="Showtimes of one movie")
def movie_showtimes(
    movie_ref: str,
    date: date_type | None = Query(default=None),
    cinema_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    movie = resolve_movie(db, movie_ref)
    stmt = (
        select(Showtime)
        .options(joinedload(Showtime.hall).joinedload(Hall.cinema), joinedload(Showtime.movie))
        .where(Showtime.movie_id == movie.id)
    )
    if date is not None:
        start, end = local_day_bounds(date)
        stmt = stmt.where(Showtime.starts_at >= start, Showtime.starts_at < end)
    else:
        stmt = stmt.where(Showtime.starts_at >= utcnow())

    if cinema_id is not None:
        stmt = stmt.join(Hall, Showtime.hall_id == Hall.id).where(Hall.cinema_id == cinema_id)

    showtimes = db.scalars(stmt.order_by(Showtime.starts_at.asc()).limit(200)).unique().all()
    return {"items": [showtime_out(showtime) for showtime in showtimes], "total": len(showtimes)}
