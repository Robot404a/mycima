"""FastAPI dependencies shared by the routers."""

from __future__ import annotations

from fastapi import Header, HTTPException, Request, status

from .services.payment_service import PaymentService


def get_payment_service(request: Request) -> PaymentService:
    service = getattr(request.app.state, "payment_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment service is not initialised.",
        )
    return service


def require_idempotency_key(
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> str:
    if idempotency_key is None or not idempotency_key.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is required.",
        )
    key = idempotency_key.strip()
    if len(key) > 128:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Idempotency-Key must be at most 128 characters.",
        )
    if any(ord(character) < 32 or ord(character) > 126 for character in key):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Idempotency-Key must contain printable ASCII characters only.",
        )
    return key
