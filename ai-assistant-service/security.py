"""JWT verification.

The gateway already rejected anonymous or expired tokens; this service decodes the
token again to learn WHO is calling, and never trusts a user id sent in a body.
"""

from __future__ import annotations

import jwt
from fastapi import Header, HTTPException, status

from config import settings

try:  # preferred: the team's shared implementation
    from shared.auth import decode_access_token, user_from_payload  # type: ignore

    USING_SHARED_AUTH = True
except ModuleNotFoundError as _exc:  # pragma: no cover - exercised when shared/ is absent
    # Fall back to local JWT decoding when shared/ is unavailable, or when a dependency it
    # needs for password hashing (bcrypt) is not installed here: this service only verifies
    # tokens, it never hashes passwords.
    if _exc.name not in ("shared", "shared.auth", "bcrypt", "jwt"):
        raise
    USING_SHARED_AUTH = False

    def decode_access_token(token: str) -> dict:
        try:
            return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        except jwt.PyJWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

    def user_from_payload(payload: dict) -> dict:
        return {
            "id": payload.get("user_id", payload.get("id", payload.get("sub"))),
            "email": payload.get("email"),
            "role": payload.get("role", "user"),
            "full_name": payload.get("full_name"),
        }


def bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def current_user(authorization: str | None = Header(default=None)) -> dict:
    token = bearer_token(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in to continue.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_from_payload(decode_access_token(token))


def optional_user(authorization: str | None = Header(default=None)) -> dict | None:
    token = bearer_token(authorization)
    if not token:
        return None
    try:
        return user_from_payload(decode_access_token(token))
    except HTTPException:
        return None
