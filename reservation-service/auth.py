"""Authentication helpers.

The gateway already verified the token and forwards the Authorization header; we decode it
again here to learn WHO is calling (never trust a user id sent in a request body).

When the team's shared/ folder arrives, `shared.auth` is used automatically.
Until then a local PyJWT fallback is used (needs JWT_SECRET / JWT_ALGORITHM to match the User service).
"""
import jwt
from fastapi import Depends, HTTPException, Request, status

import config

try:  # preferred: the team's shared implementation
    from shared.auth import decode_access_token, user_from_payload  # type: ignore
    USING_SHARED_AUTH = True
except ImportError:  # local fallback
    USING_SHARED_AUTH = False

    def decode_access_token(token: str) -> dict:
        try:
            return jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    def user_from_payload(payload: dict) -> dict:
        return {
            "id": payload.get("user_id", payload.get("id", payload.get("sub"))),
            "role": payload.get("role", "user"),
            "email": payload.get("email"),
        }


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def optional_user(request: Request) -> dict | None:
    token = _bearer_token(request)
    if not token:
        return None
    try:
        return user_from_payload(decode_access_token(token))
    except HTTPException:
        return None


def current_user(request: Request) -> dict:
    token = _bearer_token(request)
    if not token:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Sign in to continue.", headers={"WWW-Authenticate": "Bearer"}
        )
    return user_from_payload(decode_access_token(token))


def admin_user(user: dict = Depends(current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required.")
    return user


def user_id_of(user: dict) -> int:
    """Numeric user id from whichever key the token uses."""
    for key in ("id", "user_id", "sub"):
        value = user.get(key)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                break
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token does not contain a numeric user id.")
