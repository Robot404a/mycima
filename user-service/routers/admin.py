"""Administrator endpoints for user management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from database import get_db
from dependencies import require_admin
from models import User
from schemas import RoleUpdate, UserListResponse, UserOut

router = APIRouter(
    prefix="/admin/users",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=UserListResponse)
def list_users(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=120),
    db: Session = Depends(get_db),
) -> UserListResponse:
    statement = select(User)
    counter = select(func.count()).select_from(User)

    if q:
        pattern = f"%{q.strip()}%"
        condition = or_(User.email.ilike(pattern), User.full_name.ilike(pattern))
        statement = statement.where(condition)
        counter = counter.where(condition)

    total = db.scalar(counter) or 0
    users = db.scalars(
        statement.order_by(User.id).limit(limit).offset(offset)
    ).all()

    return UserListResponse(
        items=[UserOut.model_validate(user) for user in users],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db)) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )
    return user


@router.patch("/{user_id}/role", response_model=UserOut)
def update_role(
    user_id: int, payload: RoleUpdate, db: Session = Depends(get_db)
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )

    user.role = payload.role
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
