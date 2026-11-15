"""Administrator-only payment endpoints."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from ..dependencies import get_payment_service
from ..schemas import ErrorResponse, PaymentListResponse, PaymentOut, PaymentStats
from ..security import admin_user
from ..services.payment_service import PaymentService

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(admin_user)],
)

PaymentStatusQuery = Literal[
    "PENDING", "PROCESSING", "SUCCEEDED", "FAILED", "REFUND_PENDING", "REFUNDED"
]
PaymentMethodQuery = Literal["CARD", "WALLET"]


@router.get(
    "/payments",
    response_model=PaymentListResponse,
    summary="List all payments (administrators)",
)
def list_payments(
    user_id: int | None = Query(default=None, ge=1),
    status_filter: PaymentStatusQuery | None = Query(default=None, alias="status"),
    method: PaymentMethodQuery | None = Query(default=None),
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    hold_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: PaymentService = Depends(get_payment_service),
) -> PaymentListResponse:
    items, total = service.list_payments(
        user_id=user_id,
        status=status_filter,
        method=method,
        currency=currency,
        hold_id=hold_id,
        limit=limit,
        offset=offset,
    )
    return PaymentListResponse(
        items=[PaymentOut.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/payments/{payment_id}/refund",
    response_model=PaymentOut,
    summary="Simulate a full refund (administrators)",
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse, "description": "Payment is not refundable"},
    },
)
def refund_payment(
    payment_id: UUID,
    service: PaymentService = Depends(get_payment_service),
) -> PaymentOut:
    payment = service.refund(payment_id)
    return PaymentOut.model_validate(payment)


@router.get(
    "/stats",
    response_model=PaymentStats,
    summary="Payment statistics (administrators)",
)
def payment_stats(
    service: PaymentService = Depends(get_payment_service),
) -> PaymentStats:
    return PaymentStats(**service.stats())
