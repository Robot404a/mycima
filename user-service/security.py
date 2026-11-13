"""Helpers that turn a user record into a signed token response."""

from __future__ import annotations

from config import settings
from models import User
from schemas import TokenResponse, UserOut
from shared.auth import create_access_token


def build_token_response(user: User) -> TokenResponse:
    token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
        full_name=user.full_name,
        expires_minutes=settings.jwt_expire_minutes,
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
        user=UserOut.model_validate(user),
    )
