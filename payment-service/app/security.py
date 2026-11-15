"""JWT authentication shared by the REST and gRPC transports.

The token format is owned by the repository's ``shared/auth.py``: the numeric
user id is in ``sub`` and the role in ``role``. This module never trusts a user
id supplied in a request body or in custom headers.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from shared.auth import decode_access_token, user_from_payload

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    """The identity proven by the JWT, plus the raw token for downstream calls."""

    id: int
    role: str
    email: str | None
    token: str


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def authenticate_token(token: str) -> AuthenticatedUser:
    """Verify a JWT and return the authenticated identity.

    ``decode_access_token`` raises an HTTP 401 for malformed or expired tokens
    and never returns an unverified payload.
    """
    payload = decode_access_token(token)
    user = user_from_payload(payload)
    try:
        user_id = int(user["id"])
    except (TypeError, ValueError) as exc:
        raise _unauthorized("Invalid authentication token.") from exc
    if user_id <= 0:
        raise _unauthorized("Invalid authentication token.")
    return AuthenticatedUser(
        id=user_id,
        role=str(user.get("role") or "user").lower(),
        email=user.get("email"),
        token=token,
    )


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedUser:
    if credentials is None or not credentials.credentials.strip():
        raise _unauthorized("Sign in to continue.")
    return authenticate_token(credentials.credentials.strip())


def admin_user(user: AuthenticatedUser = Depends(current_user)) -> AuthenticatedUser:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )
    return user


def token_from_metadata(metadata: Iterable[tuple[str, str | bytes]] | None) -> str:
    """Read ``authorization: Bearer <jwt>`` from gRPC invocation metadata."""
    values: dict[str, str] = {}
    for key, value in metadata or ():
        if isinstance(value, bytes):
            try:
                decoded = value.decode("utf-8")
            except UnicodeDecodeError:
                continue
        else:
            decoded = value
        values[str(key).lower()] = decoded
    token = extract_bearer_token(values.get("authorization"))
    if not token:
        raise _unauthorized("Missing bearer token in gRPC metadata.")
    return token


def payload_role(payload: dict[str, Any]) -> str:
    return str(payload.get("role") or "user").lower()
