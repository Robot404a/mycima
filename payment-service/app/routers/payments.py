"""User-facing REST endpoints for creating and reading payments."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from ..dependencies import get_payment_service, require_idempotency_key
from ..schemas import (
    ErrorResponse,
    PaymentCreate,
    PaymentListResponse,
    PaymentOut,
)
from ..security import AuthenticatedUser, current_user
from ..services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["payments"])

PaymentStatusQuery = Literal[
    "PENDING", "PROCESSING", "SUCCEEDED", "FAILED", "REFUND_PENDING", "REFUNDED"
]


@router.post(
    "",
    response_model=PaymentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create and process a payment for a reservation hold",
    responses={
        200: {"description": "Idempotent replay of an existing payment"},
        400: {"model": ErrorResponse, "description": "Missing Idempotency-Key"},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse, "description": "Hold not found"},
        409: {"model": ErrorResponse, "description": "Duplicate/idempotency conflict"},
        410: {"model": ErrorResponse, "description": "Hold expired"},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse, "description": "Reservation service unavailable"},
    },
)
async def create_payment(
    payload: PaymentCreate,
    response: Response,
    user: AuthenticatedUser = Depends(current_user),
    idempotency_key: str = Depends(require_idempotency_key),
    service: PaymentService = Depends(get_payment_service),
) -> PaymentOut:
    """Charge the authoritative hold total.

    The JSON body deliberately has no amount: the only amount this service
    accepts is the one returned by the Reservation Service for ``hold_id``.
    """
    result = await service.charge(
        user_id=user.id,
        hold_id=payload.hold_id,
        token=user.token,
        method=payload.method,
        currency=payload.currency,
        simulate_outcome=payload.simulate_outcome,
        idempotency_key=idempotency_key,
    )
    response.status_code = (
        status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
    )
    return PaymentOut.model_validate(result.payment)


@router.get(
    "",
    response_model=PaymentListResponse,
    summary="List the authenticated user's payments",
)
def list_my_payments(
    status_filter: PaymentStatusQuery | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: AuthenticatedUser = Depends(current_user),
    service: PaymentService = Depends(get_payment_service),
) -> PaymentListResponse:
    items, total = service.list_payments(
        user_id=user.id, status=status_filter, limit=limit, offset=offset
    )
    return PaymentListResponse(
        items=[PaymentOut.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{payment_id}",
    response_model=PaymentOut,
    summary="Read one of the authenticated user's payments",
    responses={404: {"model": ErrorResponse}},
)
def get_payment(
    payment_id: UUID,
    user: AuthenticatedUser = Depends(current_user),
    service: PaymentService = Depends(get_payment_service),
) -> PaymentOut:
    payment = service.get_payment(payment_id, user_id=user.id)
    return PaymentOut.model_validate(payment)


@router.post(
    "/{payment_id}/retry-confirmation",
    response_model=PaymentOut,
    summary="Retry reservation confirmation without charging again",
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        503: {"model": ErrorResponse, "description": "Reservation service unavailable"},
    },
)
async def retry_confirmation(
    payment_id: UUID,
    user: AuthenticatedUser = Depends(current_user),
    service: PaymentService = Depends(get_payment_service),
) -> PaymentOut:
    payment = await service.retry_confirmation(
        payment_id, user_id=user.id, token=user.token
    )
    return PaymentOut.model_validate(payment)
