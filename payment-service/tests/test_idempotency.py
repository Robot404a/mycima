"""Idempotency, duplicate-charge prevention and concurrent request tests."""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import Payment

from .conftest import (
    USER_ID,
    idempotency_headers,
    payment_count,
)


def _detached_payment(hold_id, key: str) -> Payment:
    return Payment(
        user_id=USER_ID,
        hold_id=hold_id,
        amount=Decimal("10.00"),
        currency="MAD",
        method="CARD",
        status="PROCESSING",
        idempotency_key=key,
        request_fingerprint="x" * 64,
        confirmation_status="NOT_REQUIRED",
    )


def test_same_key_and_same_request_replays_the_payment(
    client, reservation, user_headers
):
    hold = reservation.add_hold(total="31.50")
    key = uuid.uuid4().hex
    body = {"hold_id": str(hold.id), "method": "CARD", "currency": "MAD"}

    first = client.post(
        "/payments", json=body, headers=idempotency_headers(key, user_headers)
    )
    second = client.post(
        "/payments", json=body, headers=idempotency_headers(key, user_headers)
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["transaction_ref"] == second.json()["transaction_ref"]
    assert payment_count() == 1
    assert len(reservation.get_hold_calls) == 1
    assert len(reservation.confirm_calls) == 1


def test_same_key_with_a_different_request_is_a_conflict(
    client, reservation, user_headers
):
    hold = reservation.add_hold()
    key = uuid.uuid4().hex
    first = client.post(
        "/payments",
        json={"hold_id": str(hold.id), "method": "CARD"},
        headers=idempotency_headers(key, user_headers),
    )
    assert first.status_code == 201

    different_method = client.post(
        "/payments",
        json={"hold_id": str(hold.id), "method": "WALLET"},
        headers=idempotency_headers(key, user_headers),
    )
    assert different_method.status_code == 409
    assert "different request" in different_method.json()["detail"].lower()

    other_hold = reservation.add_hold()
    different_hold = client.post(
        "/payments",
        json={"hold_id": str(other_hold.id), "method": "CARD"},
        headers=idempotency_headers(key, user_headers),
    )
    assert different_hold.status_code == 409
    assert payment_count() == 1


def test_duplicate_payment_for_the_same_hold_is_rejected(
    client, reservation, user_headers
):
    hold = reservation.add_hold(total="12.00")
    body = {"hold_id": str(hold.id), "method": "CARD"}

    first = client.post(
        "/payments", json=body, headers=idempotency_headers(base=user_headers)
    )
    second = client.post(
        "/payments", json=body, headers=idempotency_headers(base=user_headers)
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert "already exists" in second.json()["detail"].lower()
    assert payment_count() == 1
    assert len(reservation.confirm_calls) == 1


def test_failed_payment_is_replayed_without_creating_another_row(
    client, reservation, user_headers
):
    hold = reservation.add_hold(total="14.00")
    key = uuid.uuid4().hex
    body = {
        "hold_id": str(hold.id),
        "method": "CARD",
        "simulate_outcome": "failure",
    }
    first = client.post(
        "/payments", json=body, headers=idempotency_headers(key, user_headers)
    )
    second = client.post(
        "/payments", json=body, headers=idempotency_headers(key, user_headers)
    )
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["status"] == "FAILED"
    assert second.json()["failure_reason"] == "Simulated payment failure."
    assert payment_count() == 1
    assert reservation.confirm_calls == []


def _run_concurrent(
    client: TestClient, body: dict, headers_list: list[dict[str, str]]
) -> list[httpx.Response]:
    async def run() -> list[httpx.Response]:
        transport = httpx.ASGITransport(app=client.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as async_client:
            return await asyncio.gather(
                *[
                    async_client.post("/payments", json=body, headers=headers)
                    for headers in headers_list
                ]
            )

    return asyncio.run(run())


def test_concurrent_requests_with_the_same_idempotency_key_charge_once(
    client, reservation, user_headers
):
    hold = reservation.add_hold(total="88.00")
    reservation.get_hold_delay = 0.15  # both requests pass the fast path first
    key = uuid.uuid4().hex
    body = {"hold_id": str(hold.id), "method": "CARD"}
    headers = idempotency_headers(key, user_headers)

    responses = _run_concurrent(client, body, [headers, headers])

    assert sorted(response.status_code for response in responses) == [200, 201], [
        (response.status_code, response.json()) for response in responses
    ]
    ids = {response.json()["id"] for response in responses}
    assert len(ids) == 1
    assert payment_count() == 1
    assert len(reservation.confirm_calls) == 1


def test_concurrent_requests_with_different_keys_cannot_charge_twice(
    client, reservation, user_headers
):
    hold = reservation.add_hold(total="99.00")
    reservation.get_hold_delay = 0.15
    body = {"hold_id": str(hold.id), "method": "CARD"}
    headers = [
        idempotency_headers(base=user_headers),
        idempotency_headers(base=user_headers),
    ]

    responses = _run_concurrent(client, body, headers)

    assert sorted(response.status_code for response in responses) == [201, 409]
    assert payment_count() == 1
    assert len(reservation.confirm_calls) == 1


def test_database_unique_constraints_are_the_final_guard():
    """Bypass the API: the table itself rejects duplicate holds and keys."""
    hold_id = uuid.uuid4()
    with SessionLocal() as db:
        db.add(_detached_payment(hold_id, "key-one"))
        db.commit()

    with SessionLocal() as db:
        db.add(_detached_payment(hold_id, "key-two"))
        with pytest.raises(IntegrityError):
            db.commit()

    with SessionLocal() as db:
        db.add(_detached_payment(uuid.uuid4(), "key-one"))
        with pytest.raises(IntegrityError):
            db.commit()

    assert payment_count() == 1


def test_idempotency_key_is_scoped_to_the_authenticated_user(
    client, reservation, user_headers, other_headers
):
    key = uuid.uuid4().hex
    hold = reservation.add_hold()
    first = client.post(
        "/payments",
        json={"hold_id": str(hold.id), "method": "CARD"},
        headers=idempotency_headers(key, user_headers),
    )
    assert first.status_code == 201

    # The same key cannot reveal or reuse another user's payment.
    other_hold = reservation.add_hold(user_id=202)
    second = client.post(
        "/payments",
        json={"hold_id": str(other_hold.id), "method": "CARD"},
        headers=idempotency_headers(key, other_headers),
    )
    assert second.status_code == 409
    assert payment_count() == 1
