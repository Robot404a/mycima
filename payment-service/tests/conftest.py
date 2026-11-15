"""Pytest fixtures: throwaway SQLite database, fake Reservation Service, JWT helpers."""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

SERVICE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_DIR.parent
for path in (str(SERVICE_DIR), str(REPO_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

TEST_DB = Path(tempfile.gettempdir()) / f"mycima_payment_test_{os.getpid()}.db"
for suffix in ("", "-wal", "-shm"):
    candidate = Path(str(TEST_DB) + suffix)
    if candidate.exists():
        candidate.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["JWT_SECRET"] = "payment-test-secret-0123456789abcdef"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["RESERVATION_SERVICE_URL"] = "http://reservation.test"
os.environ["PAYMENT_SIMULATION_ENABLED"] = "true"
os.environ["GRPC_ENABLED"] = "false"
os.environ["SUPPORTED_CURRENCIES"] = "MAD,USD,EUR"
os.environ["DEFAULT_CURRENCY"] = "MAD"
os.environ["IDEMPOTENCY_WAIT_SECONDS"] = "3"
os.environ["IDEMPOTENCY_POLL_SECONDS"] = "0.02"
os.environ["LOG_LEVEL"] = "WARNING"

import jwt  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete, func, select  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.dependencies import get_payment_service  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Payment  # noqa: E402
from app.services.payment_service import PaymentService, PaymentSimulator  # noqa: E402
from app.services.reservation_client import (  # noqa: E402
    HoldConflict,
    HoldExpired,
    HoldInfo,
    HoldNotFound,
    ReservationUnavailable,
)

USER_ID = 101
OTHER_USER_ID = 202
ADMIN_ID = 900
TEST_SECRET = os.environ["JWT_SECRET"]


def make_token(
    user_id: int = USER_ID,
    *,
    role: str = "user",
    expires_in: int = 3600,
    secret: str = TEST_SECRET,
    subject: str | None = None,
) -> str:
    now = int(time.time())
    payload = {
        "sub": subject if subject is not None else str(user_id),
        "email": f"user{user_id}@mycima.test",
        "role": role,
        "iat": now,
        "exp": now + expires_in,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def auth_headers(
    user_id: int = USER_ID, *, role: str = "user", **token_kwargs: Any
) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {make_token(user_id, role=role, **token_kwargs)}"
    }


def idempotency_headers(
    key: str | None = None, base: dict[str, str] | None = None
) -> dict[str, str]:
    headers = dict(base or auth_headers())
    headers["Idempotency-Key"] = key or uuid.uuid4().hex
    return headers


class FakeReservationClient:
    """In-memory implementation of the two Reservation Service calls."""

    def __init__(self) -> None:
        self.holds: dict[uuid.UUID, HoldInfo] = {}
        self.get_hold_calls: list[tuple[str, str]] = []
        self.confirm_calls: list[tuple[str, str, str]] = []
        self.get_hold_error: Exception | None = None
        self.confirm_error: Exception | None = None
        self.get_hold_delay = 0.0
        self.confirm_delay = 0.0

    def add_hold(
        self,
        user_id: int = USER_ID,
        *,
        hold_id: uuid.UUID | None = None,
        total: str = "24.00",
        currency: str = "MAD",
        status: str = "active",
        expires_in: int = 600,
        seconds_left: int | None = None,
        seats: list[str] | None = None,
    ) -> HoldInfo:
        del currency  # the reservation hold contract has no currency field
        now = datetime.now(timezone.utc)
        hold = HoldInfo(
            id=hold_id or uuid.uuid4(),
            user_id=user_id,
            showtime_id=7,
            status=status,
            seats=seats or ["A1", "A2"],
            total=Decimal(total),
            expires_at=now + timedelta(seconds=expires_in),
            seconds_left=expires_in if seconds_left is None else seconds_left,
        )
        self.holds[hold.id] = hold
        return hold

    def replace_hold(self, hold: HoldInfo) -> None:
        self.holds[hold.id] = hold

    async def get_hold(self, hold_id, token: str) -> HoldInfo:
        self.get_hold_calls.append((str(hold_id), token))
        if self.get_hold_delay:
            await asyncio.sleep(self.get_hold_delay)
        if self.get_hold_error is not None:
            raise self.get_hold_error
        hold = self.holds.get(uuid.UUID(str(hold_id)))
        if hold is None:
            raise HoldNotFound("Hold not found.")
        return hold

    async def confirm_hold(self, hold_id, payment_ref: str, token: str) -> dict:
        self.confirm_calls.append((str(hold_id), payment_ref, token))
        if self.confirm_delay:
            await asyncio.sleep(self.confirm_delay)
        if self.confirm_error is not None:
            raise self.confirm_error
        hold = self.holds.get(uuid.UUID(str(hold_id)))
        if hold is None:
            raise HoldNotFound("Hold not found.")
        if hold.status == "expired":
            raise HoldExpired("This hold has expired.")
        if hold.status != "active":
            raise HoldConflict("This hold can no longer be confirmed.")
        self.holds[hold.id] = hold.model_copy(update={"status": "converted"})
        return {
            "id": str(uuid.uuid4()),
            "hold_id": str(hold.id),
            "status": "confirmed",
            "payment_ref": payment_ref,
        }


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_database(client):
    with engine.begin() as connection:
        connection.execute(delete(Payment))
    yield
    with engine.begin() as connection:
        connection.execute(delete(Payment))


@pytest.fixture()
def reservation() -> FakeReservationClient:
    return FakeReservationClient()


@pytest.fixture(autouse=True)
def service(reservation: FakeReservationClient) -> PaymentService:
    payment_service = PaymentService(
        SessionLocal,
        reservation,
        config=settings,
        simulator=PaymentSimulator(settings),
    )
    app.dependency_overrides[get_payment_service] = lambda: payment_service
    yield payment_service
    app.dependency_overrides.pop(get_payment_service, None)


@pytest.fixture()
def user_headers() -> dict[str, str]:
    return auth_headers(USER_ID)


@pytest.fixture()
def other_headers() -> dict[str, str]:
    return auth_headers(OTHER_USER_ID)


@pytest.fixture()
def admin_headers() -> dict[str, str]:
    return auth_headers(ADMIN_ID, role="admin")


@pytest.fixture()
def expired_headers() -> dict[str, str]:
    return auth_headers(USER_ID, expires_in=-60)


def payment_count() -> int:
    with SessionLocal() as db:
        return int(db.scalar(select(func.count()).select_from(Payment)) or 0)


def get_payment_row(payment_id) -> Payment | None:
    with SessionLocal() as db:
        return db.get(Payment, payment_id)


def get_payment_by_hold(hold_id) -> Payment | None:
    with SessionLocal() as db:
        return db.scalar(select(Payment).where(Payment.hold_id == hold_id))
