"""Hall endpoints, including the seat layout used to draw the SVG seat map."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Cinema, Hall
from ..schemas import HallLayoutOut, HallListOut, HallOut
from ..serializers import hall_layout, hall_out

router = APIRouter(prefix="/halls", tags=["halls"])


def _get_hall(db: Session, hall_id: int) -> Hall:
    hall = db.scalar(select(Hall).options(joinedload(Hall.cinema)).where(Hall.id == hall_id))
    if hall is None:
        raise HTTPException(status_code=404, detail="Hall not found.")
    return hall


@router.get("", response_model=HallListOut, summary="List halls, optionally by cinema")
def list_halls(
    cinema_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    stmt = (
        select(Hall)
        .options(joinedload(Hall.cinema))
        .join(Cinema, Hall.cinema_id == Cinema.id)
        .order_by(Cinema.name.asc(), Hall.name.asc())
    )
    if cinema_id is not None:
        stmt = stmt.where(Hall.cinema_id == cinema_id)
    halls = db.scalars(stmt).unique().all()
    return {"items": [hall_out(hall) for hall in halls], "total": len(halls)}


@router.get("/{hall_id}", response_model=HallOut, summary="Hall details")
def get_hall(hall_id: int, db: Session = Depends(get_db)) -> dict:
    return hall_out(_get_hall(db, hall_id))


@router.get("/{hall_id}/layout", response_model=HallLayoutOut, summary="Seat layout of the hall")
def get_hall_layout(hall_id: int, db: Session = Depends(get_db)) -> dict:
    return hall_layout(_get_hall(db, hall_id))
