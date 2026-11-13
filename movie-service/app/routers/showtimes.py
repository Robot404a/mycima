"""Showtime endpoints (seat availability lives in the reservation service)."""

from __future__ import annotations

from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Hall, Showtime
from ..schemas import ShowtimeListOut, ShowtimeOut
from ..serializers import showtime_out
from ..timeutils import local_day_bounds, utcnow

router = APIRouter(prefix="/showtimes", tags=["showtimes"])


@router.get("", response_model=ShowtimeListOut, summary="Showtimes filtered by day, movie, cinema or hall")
def list_showtimes(
    date: date_type | None = Query(default=None, description="Calendar day in the cinema timezone"),
    movie_id: int | None = None,
    cinema_id: int | None = None,
    hall_id: int | None = None,
    upcoming_only: bool = Query(default=True, description="Ignore showtimes that already started"),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(Showtime).options(
        joinedload(Showtime.hall).joinedload(Hall.cinema), joinedload(Showtime.movie)
    )
    if date is not None:
        start, end = local_day_bounds(date)
        stmt = stmt.where(Showtime.starts_at >= start, Showtime.starts_at < end)
    elif upcoming_only:
        stmt = stmt.where(Showtime.starts_at >= utcnow())

    if movie_id is not None:
        stmt = stmt.where(Showtime.movie_id == movie_id)
    if hall_id is not None:
        stmt = stmt.where(Showtime.hall_id == hall_id)
    if cinema_id is not None:
        stmt = stmt.join(Hall, Showtime.hall_id == Hall.id).where(Hall.cinema_id == cinema_id)

    showtimes = db.scalars(stmt.order_by(Showtime.starts_at.asc()).limit(limit)).unique().all()
    return {"items": [showtime_out(showtime) for showtime in showtimes], "total": len(showtimes)}


@router.get("/{showtime_id}", response_model=ShowtimeOut, summary="Single showtime with movie and hall")
def get_showtime(showtime_id: int, db: Session = Depends(get_db)) -> dict:
    showtime = db.scalar(
        select(Showtime)
        .options(joinedload(Showtime.hall).joinedload(Hall.cinema), joinedload(Showtime.movie))
        .where(Showtime.id == showtime_id)
    )
    if showtime is None:
        raise HTTPException(status_code=404, detail="Showtime not found.")
    return showtime_out(showtime)
