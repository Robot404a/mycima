"""Reservation HTTP client tests using ``httpx.MockTransport``.

These tests exercise the real ``ReservationClient`` code, including its status
code mapping, without opening a socket or requiring a teammate's service.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest

from app.services.reservation_client import (
    HoldConflict,
    HoldExpired,
    HoldNotFound,
    ReservationClient,
    ReservationRejected,
    ReservationUnavailable,
)

BASE_URL = "http://reservation.test"


def _run(handler, action):
    async def scenario():
        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = ReservationClient(BASE_URL, client=http_client)
        try:
            return await action(client)
        finally:
            await http_client.aclose()

    return asyncio.run(scenario())


def _hold_payload(hold_id, *, total="18.50", status="active"):
    now = datetime.now(timezone.utc)
    return {
        "id": str(hold_id),
        "user_id": 101,
        "showtime_id": 7,
        "status": status,
        "seats": ["A1", "A2"],
        "total": float(total),
        "expires_at": (now + timedelta(minutes=10)).isoformat(),
        "seconds_left": 600,
    }


def test_get_hold_sends_the_bearer_token_and_parses_the_total():
    hold_id = uuid4()
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["authorization"] = request.headers["authorization"]
        return httpx.Response(200, json=_hold_payload(hold_id, total="18.50"))

    hold = _run(handler, lambda client: client.get_hold(hold_id, "user-token"))

    assert seen == {
        "method": "GET",
        "path": f"/holds/{hold_id}",
        "authorization": "Bearer user-token",
    }
    assert hold.id == hold_id
    assert hold.user_id == 101
    assert hold.total == Decimal("18.5")
    assert hold.status == "active"


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (404, HoldNotFound),
        (410, HoldExpired),
        (409, HoldConflict),
        (401, ReservationRejected),
        (403, ReservationRejected),
        (500, ReservationUnavailable),
        (503, ReservationUnavailable),
    ],
)
def test_get_hold_maps_upstream_status_codes(status_code, expected):
    hold_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"detail": "raw upstream body"})

    with pytest.raises(expected) as error:
        _run(handler, lambda client: client.get_hold(hold_id, "token"))

    # The raw upstream body must never be surfaced.
    assert "raw upstream body" not in str(error.value)


def test_get_hold_maps_a_timeout_to_unavailable():
    hold_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    with pytest.raises(ReservationUnavailable):
        _run(handler, lambda client: client.get_hold(hold_id, "token"))


def test_get_hold_rejects_a_malformed_payload():
    hold_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    with pytest.raises(ReservationRejected):
        _run(handler, lambda client: client.get_hold(hold_id, "token"))


def test_confirm_hold_forwards_the_payment_reference():
    hold_id = uuid4()
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        seen["path"] = request.url.path
        seen["authorization"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(201, json={"id": str(uuid4()), "status": "confirmed"})

    result = _run(
        handler, lambda client: client.confirm_hold(hold_id, "pay_abc123", "jwt")
    )

    assert seen["path"] == f"/holds/{hold_id}/confirm"
    assert seen["authorization"] == "Bearer jwt"
    assert seen["body"] == {"payment_ref": "pay_abc123"}
    assert result["status"] == "confirmed"


def test_confirm_hold_maps_permanent_rejections():
    hold_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(410, json={"detail": "hold expired"})

    with pytest.raises(HoldExpired):
        _run(
            handler,
            lambda client: client.confirm_hold(hold_id, "pay_abc123", "jwt"),
        )
