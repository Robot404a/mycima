"""SQLAlchemy model for payments owned by this microservice."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Index,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REFUND_PENDING = "REFUND_PENDING"
    REFUNDED = "REFUNDED"


class PaymentMethod(str, enum.Enum):
    CARD = "CARD"
    WALLET = "WALLET"


class ConfirmationStatus(str, enum.Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


PAYMENT_STATUS_VALUES = tuple(item.value for item in PaymentStatus)
PAYMENT_METHOD_VALUES = tuple(item.value for item in PaymentMethod)
CONFIRMATION_STATUS_VALUES = tuple(item.value for item in ConfirmationStatus)
IN_PROGRESS_STATUSES = frozenset(
    {PaymentStatus.PENDING.value, PaymentStatus.PROCESSING.value}
)


def _in_clause(column: str) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in PAYMENT_STATUS_VALUES)})"


class Payment(Base):
    """A single simulated payment attempt for one reservation hold.

    ``hold_id`` is unique: the database, not application code, is the final
    guard against charging the same hold twice, including under concurrent
    requests. ``idempotency_key`` is unique as well (NULLs are allowed for the
    gRPC transport, which has no key in its contract).
    """

    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    hold_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, unique=True
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="MAD")
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=PaymentStatus.PENDING.value, index=True
    )
    method: Mapped[str] = mapped_column(String(12), nullable=False)

    transaction_ref: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True, unique=True
    )
    request_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)

    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Reservation confirmation is deliberately separate from payment
    # processing: a successful charge can still wait for the reservation call.
    confirmation_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ConfirmationStatus.NOT_REQUIRED.value
    )
    confirmation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmation_attempted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    refunded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(_in_clause("status"), name="ck_payments_status"),
        CheckConstraint(
            f"method IN ({', '.join(repr(value) for value in PAYMENT_METHOD_VALUES)})",
            name="ck_payments_method",
        ),
        CheckConstraint(
            f"confirmation_status IN "
            f"({', '.join(repr(value) for value in CONFIRMATION_STATUS_VALUES)})",
            name="ck_payments_confirmation_status",
        ),
        CheckConstraint("amount >= 0", name="ck_payments_amount_non_negative"),
        CheckConstraint("length(currency) = 3", name="ck_payments_currency_length"),
        Index("ix_payments_user_created", "user_id", "created_at"),
        Index("ix_payments_status_created", "status", "created_at"),
    )
