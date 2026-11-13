"""JWT and password helpers shared by every MyCima service.

The API gateway imports ``decode_access_token`` and ``user_from_payload`` from
here, so the token format is defined in exactly one place.  Every service that
issues or verifies a token must use the same ``JWT_SECRET`` environment value.
"""

from __future__ import annotations

import os
import time
from typing import Any

import bcrypt
import jwt
from fastapi import HTTPException, status

JWT_SECRET: str = os.getenv("JWT_SECRET", "mycima-dev-secret-change-me-in-production")
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "120"))

# bcrypt only considers the first 72 bytes of a password.
BCRYPT_MAX_BYTES = 72


def _credentials_error(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def hash_password(password: str) -> str:
    """Hash a plain-text password with bcrypt."""
    encoded = password.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_BYTES:
        raise ValueError(
            f"Password must be at most {BCRYPT_MAX_BYTES} bytes when UTF-8 encoded."
        )
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    """Check a plain-text password against a stored bcrypt hash."""
    if not password or not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except (ValueError, TypeError):
        # Malformed hash or password longer than 72 bytes.
        return False


def create_access_token(
    *,
    user_id: int | str,
    email: str,
    role: str = "user",
    full_name: str | None = None,
    expires_minutes: int | None = None,
) -> str:
    """Build a signed JWT for a user."""
    now = int(time.time())
    minutes = JWT_EXPIRE_MINUTES if expires_minutes is None else expires_minutes
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + minutes * 60,
    }
    if full_name:
        payload["full_name"] = full_name
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Verify a JWT and return its payload, or raise HTTP 401."""
    if not token:
        raise _credentials_error("Invalid or expired authentication token.")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise _credentials_error("Authentication token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise _credentials_error("Invalid or expired authentication token.") from exc
    if not payload.get("sub"):
        raise _credentials_error("Invalid or expired authentication token.")
    return payload


def user_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalise a decoded JWT payload into the user object used by services."""
    return {
        "id": payload.get("sub"),
        "email": payload.get("email"),
        "role": payload.get("role", "user"),
        "full_name": payload.get("full_name"),
    }
