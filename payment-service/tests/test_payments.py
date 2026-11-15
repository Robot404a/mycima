"""Functional REST tests: success, failure, security, ownership and admin."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.config import Settings, settings as app_settings
from app.database import SessionLocal
from app.main import app
from app.dependencies import get_payment_service
from app.services.payment_service import PaymentService, PaymentSimulator
from app.services.reservation_client import ReservationUnavailable

from .conftest import (
    ADMIN_ID,
    OTHER_USER_ID,
    USER_ID,
    FakeReservationClient,
    auth_headers,
    get_payment_row,
    idempotency_headers,
    payment_count,
)


def create_payment(
    client: TestClient,
    reservation: FakeReservationClient,
    headers: dict[str, str],
    *,
    key: str | None = None,
    total: str = "24.00",
    method: str = "CARD",
    currency: str = "MAD",
    hold_id=None,
    simulate_outcome: str | None = None,
    owner_id: int = USER_ID,
):
    hold = reservation.add_hold(
        user_id=owner_id, hold_id=hold_id, total=total
    ) if hold_id is None else reservation.holds[hold_id]
    body = {
        "hold_id": str(hold.id),
        "method": method,
        "currency": currency,
    }
    if simulate_outcome is not None:
        body["simulate_outcome"] = simulate_outcome
    return client.post(
        "/payments",
        json=body,
        headers=idempotency_headers(key, headers),
    )


def test_health_reports_database_and_disabled_grpc(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["database"] == "up"
    assert response.json()["grpc"] == "disabled"


def test_successful_payment_uses_reservation_amount_and_confirms(
    client, reservation, user_headers
):
    response = create_payment(
        client, reservation, user_headers, total="42.75", method="WALLET"
    )
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["status"] == "SUCCEEDED"
    assert body["amount"] == "42.75"
    assert body["currency"] == "MAD"
    assert body["method"] == "WALLET"
    assert body["transaction_ref"].startswith("pay_")
    assert body["confirmation_status"] == "CONFIRMED"
    assert body["confirmation_error"] is None
    assert body["processed_at"] is not None
    assert body["user_id"] == USER_ID
    assert body["hold_id"] == str(reservation.get_hold_calls[0][0])

    assert len(reservation.confirm_calls) == 1
    confirmed_hold, payment_ref, token = reservation.confirm_calls[0]
    assert confirmed_hold == body["hold_id"]
    assert payment_ref == body["transaction_ref"]
    assert token
    assert payment_count() == 1
    assert f"{get_payment_row(uuid.UUID(body['id'])).amount:.2f}" == body["amount"]


def test_failed_payment_is_recorded_without_confirmation(
    client, reservation, user_headers
):
    response = create_payment(
        client, reservation, user_headers, simulate_outcome="failure"
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "FAILED"
    assert body["failure_reason"] == "Simulated payment failure."
    assert body["transaction_ref"] is None
    assert body["confirmation_status"] == "NOT_REQUIRED"
    assert reservation.confirm_calls == []
    assert payment_count() == 1


def test_missing_and_invalid_jwt_are_rejected(client, reservation):
    hold = reservation.add_hold()
    body = {"hold_id": str(hold.id), "method": "CARD"}

    missing = client.post(
        "/payments", json=body, headers={"Idempotency-Key": uuid.uuid4().hex}
    )
    assert missing.status_code == 401

    malformed = client.post(
        "/payments",
        json=body,
        headers={
            "Idempotency-Key": uuid.uuid4().hex,
            "Authorization": "Bearer not-a-jwt",
        },
    )
    assert malformed.status_code == 401

    wrong_secret = auth_headers(USER_ID, secret="attacker-secret")
    rejected = client.post(
        "/payments", json=body, headers=idempotency_headers(base=wrong_secret)
    )
    assert rejected.status_code == 401
    assert reservation.get_hold_calls == []


def test_expired_jwt_is_rejected(client, reservation, expired_headers):
    hold = reservation.add_hold()
    response = client.post(
        "/payments",
        json={"hold_id": str(hold.id), "method": "CARD"},
        headers=idempotency_headers(base=expired_headers),
    )
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()
    assert reservation.get_hold_calls == []


def test_non_numeric_subject_is_rejected(client, reservation):
    hold = reservation.add_hold()
    headers = auth_headers(subject="not-a-number")
    response = client.post(
        "/payments",
        json={"hold_id": str(hold.id), "method": "CARD"},
        headers=idempotency_headers(base=headers),
    )
    assert response.status_code == 401


def test_invalid_hold_returns_404(client, service, user_headers):
    hold_id = uuid.uuid4()
    response = client.post(
        "/payments",
        json={"hold_id": str(hold_id), "method": "CARD"},
        headers=idempotency_headers(base=user_headers),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Hold not found."
    assert payment_count() == 0


def test_expired_hold_returns_410(client, reservation, user_headers):
    hold = reservation.add_hold(status="expired")
    response = client.post(
        "/payments",
        json={"hold_id": str(hold.id), "method": "CARD"},
        headers=idempotency_headers(base=user_headers),
    )
    assert response.status_code == 410
    assert payment_count() == 0
    assert reservation.confirm_calls == []


def test_hold_that_expires_by_clock_returns_410(client, reservation, user_headers):
    hold = reservation.add_hold(expires_in=-30)
    response = client.post(
        "/payments",
        json={"hold_id": str(hold.id), "method": "CARD"},
        headers=idempotency_headers(base=user_headers),
    )
    assert response.status_code == 410
    assert payment_count() == 0


def test_inactive_hold_returns_409(client, reservation, user_headers):
    hold = reservation.add_hold(status="released")
    response = client.post(
        "/payments",
        json={"hold_id": str(hold.id), "method": "CARD"},
        headers=idempotency_headers(base=user_headers),
    )
    assert response.status_code == 409
    assert payment_count() == 0


def test_hold_owned_by_somebody_else_is_not_found(
    client, reservation, user_headers
):
    hold = reservation.add_hold(user_id=OTHER_USER_ID)
    response = client.post(
        "/payments",
        json={"hold_id": str(hold.id), "method": "CARD"},
        headers=idempotency_headers(base=user_headers),
    )
    assert response.status_code == 404
    assert payment_count() == 0


def test_client_supplied_amount_is_rejected(client, reservation, user_headers):
    hold = reservation.add_hold(total="30.00")
    response = client.post(
        "/payments",
        json={
            "hold_id": str(hold.id),
            "method": "CARD",
            "amount": "0.01",
        },
        headers=idempotency_headers(base=user_headers),
    )
    assert response.status_code == 422
    assert reservation.get_hold_calls == []
    assert payment_count() == 0


def test_amount_comes_from_the_reservation_hold_not_the_request(
    client, reservation, user_headers
):
    hold = reservation.add_hold(total="19.99")
    response = client.post(
        "/payments",
        json={"hold_id": str(hold.id), "method": "CARD"},
        headers=idempotency_headers(base=user_headers),
    )
    assert response.status_code == 201, response.text
    assert response.json()["amount"] == "19.99"
    row = get_payment_row(uuid.UUID(response.json()["id"]))
    assert str(row.amount) == "19.99"


def test_unsupported_currency_is_rejected(client, reservation, user_headers):
    hold = reservation.add_hold()
    response = client.post(
        "/payments",
        json={"hold_id": str(hold.id), "method": "CARD", "currency": "GBP"},
        headers=idempotency_headers(base=user_headers),
    )
    assert response.status_code == 422
    assert payment_count() == 0


def test_unsupported_method_is_rejected(client, reservation, user_headers):
    hold = reservation.add_hold()
    response = client.post(
        "/payments",
        json={"hold_id": str(hold.id), "method": "CASH"},
        headers=idempotency_headers(base=user_headers),
    )
    assert response.status_code == 422


def test_simulation_outcome_is_rejected_when_disabled(
    client, reservation, user_headers
):
    disabled = Settings(
        payment_simulation_enabled=False,
        database_url=app_settings.database_url,
        grpc_enabled=False,
        supported_currencies=app_settings.supported_currencies,
    )
    disabled_service = PaymentService(
        SessionLocal,
        reservation,
        config=disabled,
        simulator=PaymentSimulator(disabled),
    )
    app.dependency_overrides[get_payment_service] = lambda: disabled_service
    try:
        hold = reservation.add_hold()
        response = client.post(
            "/payments",
            json={
                "hold_id": str(hold.id),
                "method": "CARD",
                "simulate_outcome": "success",
            },
            headers=idempotency_headers(base=user_headers),
        )
        assert response.status_code == 422
        assert "simulation" in response.json()["detail"].lower()
        assert payment_count() == 0
    finally:
        app.dependency_overrides.pop(get_payment_service, None)


def test_reservation_unavailable_before_charge_returns_503_and_no_payment(
    client, reservation, user_headers
):
    reservation.get_hold_error = ReservationUnavailable("down")
    response = create_payment(client, reservation, user_headers)
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()
    assert payment_count() == 0


def test_confirmation_failure_keeps_success_and_can_be_retried(
    client, reservation, user_headers
):
    reservation.confirm_error = ReservationUnavailable("reservation down")
    response = create_payment(client, reservation, user_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "SUCCEEDED"
    assert body["confirmation_status"] == "PENDING"
    assert body["confirmation_error"]
    payment_id = body["id"]
    transaction_ref = body["transaction_ref"]
    get_calls_after_charge = len(reservation.get_hold_calls)

    # The reservation service comes back: retrying confirms the same charge.
    reservation.confirm_error = None
    retry = client.post(
        f"/payments/{payment_id}/retry-confirmation", headers=user_headers
    )
    assert retry.status_code == 200, retry.text
    retried = retry.json()
    assert retried["id"] == payment_id
    assert retried["transaction_ref"] == transaction_ref
    assert retried["confirmation_status"] == "CONFIRMED"
    assert retried["status"] == "SUCCEEDED"
    assert len(reservation.confirm_calls) == 2
    assert len(reservation.get_hold_calls) == get_calls_after_charge
    assert payment_count() == 1
    assert len({call[1] for call in reservation.confirm_calls}) == 1  # same ref


def test_retry_confirmation_on_confirmed_payment_does_not_call_again(
    client, reservation, user_headers
):
    response = create_payment(client, reservation, user_headers)
    payment_id = response.json()["id"]
    assert response.json()["confirmation_status"] == "CONFIRMED"
    before = len(reservation.confirm_calls)

    retry = client.post(
        f"/payments/{payment_id}/retry-confirmation", headers=user_headers
    )
    assert retry.status_code == 200
    assert retry.json()["confirmation_status"] == "CONFIRMED"
    assert len(reservation.confirm_calls) == before


def test_payment_listing_is_scoped_to_the_authenticated_user(
    client, reservation, user_headers, other_headers
):
    first = create_payment(client, reservation, user_headers, total="10.00")
    second = create_payment(client, reservation, user_headers, total="20.00")
    third = create_payment(
        client, reservation, other_headers, total="30.00", owner_id=OTHER_USER_ID
    )
    assert {first.status_code, second.status_code, third.status_code} == {201}

    mine = client.get("/payments", headers=user_headers)
    assert mine.status_code == 200
    assert mine.json()["total"] == 2
    assert {item["id"] for item in mine.json()["items"]} == {
        first.json()["id"],
        second.json()["id"],
    }

    theirs = client.get("/payments", headers=other_headers)
    assert theirs.json()["total"] == 1

    hidden = client.get(
        f"/payments/{first.json()['id']}", headers=other_headers
    )
    assert hidden.status_code == 404

    hidden_retry = client.post(
        f"/payments/{first.json()['id']}/retry-confirmation",
        headers=other_headers,
    )
    assert hidden_retry.status_code == 404


def test_admin_refund_is_idempotent_and_admin_only(
    client, reservation, user_headers, admin_headers, other_headers
):
    created = create_payment(client, reservation, user_headers)
    payment_id = created.json()["id"]

    forbidden = client.post(
        f"/admin/payments/{payment_id}/refund", headers=user_headers
    )
    assert forbidden.status_code == 403

    refund = client.post(
        f"/admin/payments/{payment_id}/refund", headers=admin_headers
    )
    assert refund.status_code == 200, refund.text
    assert refund.json()["status"] == "REFUNDED"
    assert refund.json()["refunded_at"] is not None

    again = client.post(
        f"/admin/payments/{payment_id}/refund", headers=admin_headers
    )
    assert again.status_code == 200
    assert again.json()["status"] == "REFUNDED"

    failed = create_payment(
        client, reservation, user_headers, simulate_outcome="failure"
    )
    cannot_refund = client.post(
        f"/admin/payments/{failed.json()['id']}/refund", headers=admin_headers
    )
    assert cannot_refund.status_code == 409
    assert other_headers  # the other user is deliberately not an administrator


def test_admin_list_and_stats(
    client, reservation, user_headers, admin_headers
):
    succeeded = create_payment(client, reservation, user_headers, total="24.00")
    failed = create_payment(
        client, reservation, user_headers, total="50.00", simulate_outcome="failure"
    )
    assert succeeded.status_code == 201 and failed.status_code == 201
    assert client.post(
        f"/admin/payments/{succeeded.json()['id']}/refund", headers=admin_headers
    ).status_code == 200

    listed = client.get("/admin/payments", headers=admin_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 2

    filtered = client.get(
        "/admin/payments",
        params={"status": "FAILED", "user_id": USER_ID},
        headers=admin_headers,
    )
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["status"] == "FAILED"

    stats = client.get("/admin/stats", headers=admin_headers)
    assert stats.status_code == 200, stats.text
    body = stats.json()
    assert body["total_payments"] == 2
    assert body["by_status"]["SUCCEEDED"] == 0
    assert body["by_status"]["FAILED"] == 1
    assert body["by_status"]["REFUNDED"] == 1
    assert body["succeeded_count"] == 0
    assert body["failed_count"] == 1
    assert body["refunded_count"] == 1
    assert body["gross_amount"] == "24.00"
    assert body["refunded_amount"] == "24.00"
    assert body["net_amount"] == "0.00"

    forbidden = client.get("/admin/stats", headers=user_headers)
    assert forbidden.status_code == 403


def test_idempotency_key_header_is_required(client, reservation, user_headers):
    hold = reservation.add_hold()
    response = client.post(
        "/payments",
        json={"hold_id": str(hold.id), "method": "CARD"},
        headers=user_headers,
    )
    assert response.status_code == 400
    assert "Idempotency-Key" in response.json()["detail"]
    assert payment_count() == 0
