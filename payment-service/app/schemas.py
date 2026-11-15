"""Pydantic v2 request and response models for the REST API."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from .config import settings

PaymentMethodLiteral = Literal["CARD", "WALLET"]
SimulationLiteral = Literal["success", "failure"]


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


class PaymentCreate(BaseModel):
    """Body for ``POST /payments``.

    There is intentionally no ``amount`` field and extra keys are forbidden:
    the only trustworthy amount is the one returned by the Reservation Service.
    """

    model_config = ConfigDict(extra="forbid")

    hold_id: UUID
    method: PaymentMethodLiteral
    currency: str = Field(
        default_factory=lambda: settings.default_currency, min_length=3, max_length=3
    )
    simulate_outcome: SimulationLiteral | None = Field(
        default=None,
        description=(
            "Development/test only. Rejected unless PAYMENT_SIMULATION_ENABLED=true."
        ),
    )

    @field_validator("currency")
    @classmethod
    def normalise_currency(cls, value: str) -> str:
        return value.strip().upper()


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: int
    hold_id: UUID
    amount: Decimal
    currency: str
    status: str
    method: str
    transaction_ref: str | None
    failure_reason: str | None
    confirmation_status: str
    confirmation_error: str | None
    confirmation_attempted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None
    refunded_at: datetime | None

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> str:
        return _money(value)


class PaymentListResponse(BaseModel):
    items: list[PaymentOut]
    total: int
    limit: int
    offset: int


class PaymentStats(BaseModel):
    total_payments: int
    by_status: dict[str, int]
    by_method: dict[str, int]
    by_currency: dict[str, int]
    succeeded_count: int
    failed_count: int
    refunded_count: int
    pending_confirmations: int
    gross_amount: Decimal
    refunded_amount: Decimal
    net_amount: Decimal

    @field_serializer("gross_amount", "refunded_amount", "net_amount")
    def serialize_money(self, value: Decimal) -> str:
        return _money(value)


class HealthResponse(BaseModel):
    status: str
    service: str
    database: str
    grpc: str


class ErrorResponse(BaseModel):
    detail: str
