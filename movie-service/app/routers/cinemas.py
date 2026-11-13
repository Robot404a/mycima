"""Cinema endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import Cinema
from ..schemas import CinemaListOut, CinemaOut
from ..serializers import cinema_out, hall_out

router = APIRouter(prefix="/cinemas", tags=["cinemas"])


@router.get("", response_model=CinemaListOut, summary="List cinemas, optionally by city")
def list_cinemas(city: str | None = Query(default=None), db: Session = Depends(get_db)) -> dict:
    stmt = select(Cinema).order_by(Cinema.city.asc(), Cinema.name.asc())
    if city:
        stmt = stmt.where(Cinema.city.ilike(city.strip()))
    cinemas = db.scalars(stmt).all()
    return {"items": [cinema_out(cinema) for cinema in cinemas], "total": len(cinemas)}


@router.get("/{cinema_id}", summary="Cinema with its halls")
def get_cinema(cinema_id: int, db: Session = Depends(get_db)) -> dict:
    cinema = db.scalar(select(Cinema).options(selectinload(Cinema.halls)).where(Cinema.id == cinema_id))
    if cinema is None:
        raise HTTPException(status_code=404, detail="Cinema not found.")
    payload = cinema_out(cinema)
    payload["halls"] = [hall_out(hall) for hall in cinema.halls]
    return payload
