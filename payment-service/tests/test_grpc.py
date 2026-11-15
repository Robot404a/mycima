"""End-to-end gRPC tests over a real loopback gRPC server."""

from __future__ import annotations

import asyncio
import uuid

import grpc
import pytest

from app import config as _config  # noqa: F401 - generated/ on sys.path
import payment_pb2 as payment_pb2  # noqa: E402
import payment_pb2_grpc as payment_pb2_grpc  # noqa: E402
from app.config import settings  # noqa: E402
from app.grpc_server import GrpcServer  # noqa: E402
from app.services.payment_service import SimulationOutcome  # noqa: E402
from app.services.reservation_client import ReservationUnavailable  # noqa: E402

from .conftest import (  # noqa: E402
    OTHER_USER_ID,
    USER_ID,
    FakeReservationClient,
    get_payment_by_hold,
    make_token,
    payment_count,
)


def metadata_for(
    user_id: int = USER_ID,
    *,
    token: str | None = None,
    extra: tuple[tuple[str, str], ...] = (),
):
    bearer = token or make_token(user_id)
    return (("authorization", f"Bearer {bearer}"), *extra)


async def _charge(
    service,
    *,
    request: payment_pb2.ChargeRequest,
    metadata,
    timeout: float = 10.0,
):
    server = GrpcServer(service, host="127.0.0.1", port=0, config=settings)
    port = await server.start()
    try:
        async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            stub = payment_pb2_grpc.PaymentServiceStub(channel)
            return await stub.Charge(request, metadata=metadata, timeout=timeout)
    finally:
        await server.stop(grace_seconds=0)


def charge(service, request, metadata=None, timeout: float = 10.0):
    return asyncio.run(
        _charge(
            service,
            request=request,
            metadata=metadata if metadata is not None else metadata_for(),
            timeout=timeout,
        )
    )


def test_grpc_charge_success_ignores_client_amount(
    service, reservation: FakeReservationClient
):
    hold = reservation.add_hold(total="73.25")
    request = payment_pb2.ChargeRequest(
        hold_id=str(hold.id), amount="0.01", currency="MAD"
    )

    response = charge(service, request)

    assert response.status == "SUCCEEDED"
    assert response.transaction_id.startswith("pay_")
    assert response.amount == "73.25"  # authoritative hold total, not 0.01
    assert response.currency == "MAD"
    assert response.failure_reason == ""
    assert response.processed_at
    assert len(reservation.confirm_calls) == 1
    assert reservation.confirm_calls[0][1] == response.transaction_id
    assert payment_count() == 1
    row = get_payment_by_hold(hold.id)
    assert row is not None
    assert row.user_id == USER_ID
    assert str(row.amount) == "73.25"


def test_grpc_charge_failure_returns_failed_response(
    service, reservation: FakeReservationClient
):
    hold = reservation.add_hold(total="12.00")

    class DecliningSimulator:
        def evaluate(self, **kwargs):
            return SimulationOutcome(False, "Simulated card decline.")

    service.simulator = DecliningSimulator()
    response = charge(
        service,
        payment_pb2.ChargeRequest(
            hold_id=str(hold.id), amount="12.00", currency="MAD"
        ),
    )

    assert response.status == "FAILED"
    assert response.failure_reason == "Simulated card decline."
    assert response.transaction_id == ""
    assert response.amount == "12.00"
    assert reservation.confirm_calls == []
    assert payment_count() == 1


def test_grpc_requires_metadata_jwt(service, reservation):
    hold = reservation.add_hold()
    request = payment_pb2.ChargeRequest(
        hold_id=str(hold.id), amount="1.00", currency="MAD"
    )

    with pytest.raises(grpc.aio.AioRpcError) as missing:
        charge(service, request, metadata=())
    assert missing.value.code() == grpc.StatusCode.UNAUTHENTICATED
    assert payment_count() == 0

    with pytest.raises(grpc.aio.AioRpcError) as invalid:
        charge(service, request, metadata=(("authorization", "Bearer nope"),))
    assert invalid.value.code() == grpc.StatusCode.UNAUTHENTICATED

    with pytest.raises(grpc.aio.AioRpcError) as expired:
        charge(
            service,
            request,
            metadata=metadata_for(token=make_token(expires_in=-60)),
        )
    assert expired.value.code() == grpc.StatusCode.UNAUTHENTICATED


def test_grpc_rejects_invalid_hold_id(service):
    request = payment_pb2.ChargeRequest(
        hold_id="not-a-uuid", amount="10.00", currency="MAD"
    )
    with pytest.raises(grpc.aio.AioRpcError) as error:
        charge(service, request)
    assert error.value.code() == grpc.StatusCode.INVALID_ARGUMENT


def test_grpc_unknown_hold_is_not_found(service):
    request = payment_pb2.ChargeRequest(
        hold_id=str(uuid.uuid4()), amount="10.00", currency="MAD"
    )
    with pytest.raises(grpc.aio.AioRpcError) as error:
        charge(service, request)
    assert error.value.code() == grpc.StatusCode.NOT_FOUND


def test_grpc_expired_hold_is_failed_precondition(service, reservation):
    hold = reservation.add_hold(status="expired")
    request = payment_pb2.ChargeRequest(
        hold_id=str(hold.id), amount="10.00", currency="MAD"
    )
    with pytest.raises(grpc.aio.AioRpcError) as error:
        charge(service, request)
    assert error.value.code() == grpc.StatusCode.FAILED_PRECONDITION
    assert payment_count() == 0


def test_grpc_unsupported_currency_is_invalid_argument(service, reservation):
    hold = reservation.add_hold()
    request = payment_pb2.ChargeRequest(
        hold_id=str(hold.id), amount="10.00", currency="GBP"
    )
    with pytest.raises(grpc.aio.AioRpcError) as error:
        charge(service, request)
    assert error.value.code() == grpc.StatusCode.INVALID_ARGUMENT


def test_grpc_reservation_unavailable(service, reservation):
    hold = reservation.add_hold()
    reservation.get_hold_error = ReservationUnavailable("down")
    request = payment_pb2.ChargeRequest(
        hold_id=str(hold.id), amount="10.00", currency="MAD"
    )
    with pytest.raises(grpc.aio.AioRpcError) as error:
        charge(service, request)
    assert error.value.code() == grpc.StatusCode.UNAVAILABLE
    assert payment_count() == 0


def test_grpc_duplicate_hold_replays_existing_transaction(
    service, reservation: FakeReservationClient
):
    hold = reservation.add_hold(total="55.00")
    request = payment_pb2.ChargeRequest(
        hold_id=str(hold.id), amount="55.00", currency="MAD"
    )

    first = charge(service, request)
    second = charge(service, request)

    assert first.status == "SUCCEEDED"
    assert second.status == "SUCCEEDED"
    assert second.transaction_id == first.transaction_id
    assert payment_count() == 1
    assert len(reservation.confirm_calls) == 1


def test_grpc_never_trusts_a_user_id_supplied_in_metadata(
    service, reservation
):
    hold = reservation.add_hold(user_id=OTHER_USER_ID)
    request = payment_pb2.ChargeRequest(
        hold_id=str(hold.id), amount="10.00", currency="MAD"
    )
    metadata = metadata_for(
        USER_ID, extra=(("x-user-id", str(OTHER_USER_ID)),)
    )
    with pytest.raises(grpc.aio.AioRpcError) as error:
        charge(service, request, metadata=metadata)
    assert error.value.code() == grpc.StatusCode.NOT_FOUND
    assert payment_count() == 0


def test_grpc_default_currency_when_field_is_empty(service, reservation):
    hold = reservation.add_hold(total="9.00")
    request = payment_pb2.ChargeRequest(
        hold_id=str(hold.id), amount="", currency=""
    )
    response = charge(service, request)
    assert response.status == "SUCCEEDED"
    assert response.currency == settings.default_currency
    assert response.amount == "9.00"
