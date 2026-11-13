"""Admin endpoints (JWT with role=admin, forwarded by the gateway)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Cinema, Hall, Movie, Showtime
from ..schemas import (
    CinemaCreate,
    CinemaOut,
    HallCreate,
    HallOut,
    MovieCreate,
    MovieOut,
    MovieUpdate,
    ShowtimeCreate,
    ShowtimeOut,
)
from ..security import require_admin
from ..seed_data import FORMAT_BY_SCREEN_TYPE, PRICES_BY_SCREEN_TYPE
from ..serializers import cinema_out, hall_out, movie_out, showtime_out
from ..utils import slugify
from ..timeutils import to_utc_naive

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.post("/movies", response_model=MovieOut, status_code=status.HTTP_201_CREATED, summary="Add a movie")
def create_movie(payload: MovieCreate, db: Session = Depends(get_db)) -> dict:
    slug = slugify(payload.slug or payload.title)
    if db.scalar(select(Movie.id).where(Movie.slug == slug)):
        raise HTTPException(status_code=409, detail=f"A movie with slug '{slug}' already exists.")
    data = payload.model_dump(exclude={"slug"})
    movie = Movie(slug=slug, **data)
    movie.sync_keys()
    db.add(movie)
    db.commit()
    db.refresh(movie)
    return movie_out(movie)


@router.patch("/movies/{movie_id}", response_model=MovieOut, summary="Update a movie")
def update_movie(movie_id: int, payload: MovieUpdate, db: Session = Depends(get_db)) -> dict:
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found.")
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(movie, key, value)
    movie.sync_keys()
    db.commit()
    db.refresh(movie)
    return movie_out(movie)


@router.delete("/movies/{movie_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a movie")
def delete_movie(movie_id: int, db: Session = Depends(get_db)) -> Response:
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found.")
    db.delete(movie)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/showtimes", response_model=ShowtimeOut, status_code=status.HTTP_201_CREATED, summary="Schedule a showtime")
def create_showtime(payload: ShowtimeCreate, db: Session = Depends(get_db)) -> dict:
    movie = db.get(Movie, payload.movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found.")
    hall = db.get(Hall, payload.hall_id)
    if hall is None:
        raise HTTPException(status_code=404, detail="Hall not found.")

    starts_at = to_utc_naive(payload.starts_at)
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
        price_cents=payload.price_cents
        if payload.price_cents is not None
        else PRICES_BY_SCREEN_TYPE.get(hall.screen_type, 5000),
        language=payload.language,
        format=payload.format or FORMAT_BY_SCREEN_TYPE.get(hall.screen_type, "2D"),
    )
    db.add(showtime)
    db.commit()
    showtime = db.scalar(
        select(Showtime)
        .options(joinedload(Showtime.hall).joinedload(Hall.cinema), joinedload(Showtime.movie))
        .where(Showtime.id == showtime.id)
    )
    return showtime_out(showtime)


@router.delete("/showtimes/{showtime_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Cancel a showtime")
def delete_showtime(showtime_id: int, db: Session = Depends(get_db)) -> Response:
    showtime = db.get(Showtime, showtime_id)
    if showtime is None:
        raise HTTPException(status_code=404, detail="Showtime not found.")
    db.delete(showtime)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/cinemas", response_model=CinemaOut, status_code=status.HTTP_201_CREATED, summary="Add a cinema")
def create_cinema(payload: CinemaCreate, db: Session = Depends(get_db)) -> dict:
    if db.scalar(select(Cinema.id).where(Cinema.name == payload.name)):
        raise HTTPException(status_code=409, detail="A cinema with that name already exists.")
    cinema = Cinema(**payload.model_dump())
    db.add(cinema)
    db.commit()
    db.refresh(cinema)
    return cinema_out(cinema)


@router.post("/halls", response_model=HallOut, status_code=status.HTTP_201_CREATED, summary="Add a hall")
def create_hall(payload: HallCreate, db: Session = Depends(get_db)) -> dict:
    cinema = db.get(Cinema, payload.cinema_id)
    if cinema is None:
        raise HTTPException(status_code=404, detail="Cinema not found.")
    duplicate = db.scalar(
        select(Hall.id).where(Hall.cinema_id == cinema.id, Hall.name == payload.name)
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="This cinema already has a hall with that name.")
    hall = Hall(**payload.model_dump())
    db.add(hall)
    db.commit()
    hall = db.scalar(select(Hall).options(joinedload(Hall.cinema)).where(Hall.id == hall.id))
    return hall_out(hall)


@router.delete("/halls/{hall_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a hall")
def delete_hall(hall_id: int, db: Session = Depends(get_db)) -> Response:
    hall = db.get(Hall, hall_id)
    if hall is None:
        raise HTTPException(status_code=404, detail="Hall not found.")
    db.delete(hall)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
