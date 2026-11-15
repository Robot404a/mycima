"""Async gRPC implementation of ``nocturne.payment.PaymentService``.

The protobuf contract is treated as immutable. The ``amount`` field is
intentionally ignored, and authentication comes from ``authorization`` gRPC
metadata, never from the request message.
"""

from __future__ import annotations

import logging

import grpc
from fastapi import HTTPException

from . import config as _config  # noqa: F401 - sets up generated/ on sys.path
import payment_pb2 as payment_pb2  # noqa: E402
import payment_pb2_grpc as payment_pb2_grpc  # noqa: E402

from .config import Settings, settings as default_settings  # noqa: E402
from .security import authenticate_token, token_from_metadata  # noqa: E402
from .services.payment_service import (  # noqa: E402
    PaymentConflict,
    PaymentDependencyError,
    PaymentGone,
    PaymentNotFound,
    PaymentService,
    PaymentServiceError,
    PaymentUnavailable,
    PaymentValidationError,
)

logger = logging.getLogger("payment-service.grpc")

_STATUS_MAP = {
    400: grpc.StatusCode.INVALID_ARGUMENT,
    401: grpc.StatusCode.UNAUTHENTICATED,
    403: grpc.StatusCode.PERMISSION_DENIED,
    404: grpc.StatusCode.NOT_FOUND,
    409: grpc.StatusCode.FAILED_PRECONDITION,
    410: grpc.StatusCode.FAILED_PRECONDITION,
    422: grpc.StatusCode.INVALID_ARGUMENT,
    502: grpc.StatusCode.UNAVAILABLE,
    503: grpc.StatusCode.UNAVAILABLE,
}


def _status_for(code: int) -> grpc.StatusCode:
    return _STATUS_MAP.get(code, grpc.StatusCode.INTERNAL)


class PaymentServicer(payment_pb2_grpc.PaymentServiceServicer):
    def __init__(
        self,
        service: PaymentService,
        *,
        config: Settings | None = None,
    ) -> None:
        self.service = service
        self.settings = config or default_settings

    async def Charge(self, request, context):  # noqa: N802 - protobuf method name
        try:
            token = token_from_metadata(context.invocation_metadata())
            user = authenticate_token(token)
            metadata = {
                str(key).lower(): value
                for key, value in (context.invocation_metadata() or ())
            }
            method = str(metadata.get("x-payment-method") or self.settings.grpc_default_method)
            currency = (request.currency or "").strip().upper() or None

            # request.amount is deliberately not read. It is untrusted and may
            # be empty, malformed, negative, or simply different from the hold.
            result = await self.service.charge(
                user_id=user.id,
                hold_id=request.hold_id,
                token=user.token,
                method=method,
                currency=currency,
                simulate_outcome=None,
                idempotency_key=None,
                replay_existing_hold=True,
            )
            return self._response(result.payment)
        except HTTPException as exc:
            await context.abort(_status_for(exc.status_code), exc.detail)
        except PaymentValidationError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, exc.detail)
        except PaymentNotFound as exc:
            await context.abort(grpc.StatusCode.NOT_FOUND, exc.detail)
        except (PaymentGone, PaymentConflict) as exc:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, exc.detail)
        except (PaymentUnavailable, PaymentDependencyError) as exc:
            await context.abort(grpc.StatusCode.UNAVAILABLE, exc.detail)
        except PaymentServiceError as exc:
            await context.abort(_status_for(exc.status_code), exc.detail)
        except Exception:  # noqa: BLE001 - never leak internals over the wire
            logger.exception("unhandled error in gRPC Charge")
            await context.abort(
                grpc.StatusCode.INTERNAL, "Internal payment service error."
            )

    @staticmethod
    def _response(payment) -> payment_pb2.ChargeResponse:
        processed = payment.processed_at or payment.created_at
        return payment_pb2.ChargeResponse(
            transaction_id=payment.transaction_ref or "",
            status=payment.status,
            failure_reason=payment.failure_reason or "",
            amount=f"{payment.amount:.2f}",
            currency=payment.currency,
            processed_at=processed.isoformat() if processed else "",
        )
