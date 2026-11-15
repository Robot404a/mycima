"""Shared payment business logic used by both REST and gRPC.

The important invariants live here, not in the transports:

* the amount is always the authoritative total returned by the Reservation
  Service; client amounts are never read;
* ``payments.hold_id`` is unique, so two concurrent requests cannot both charge
  the same hold;
* idempotency keys are unique and fingerprinted, so replays return the original
  payment and mismatched retries get HTTP 409;
* no database transaction is held while an HTTP call is in flight;
* reservation confirmation is a separate, retryable step after a successful
  charge and never starts another charge.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from ..config import Settings, settings as default_settings
from ..models import (
    IN_PROGRESS_STATUSES,
    ConfirmationStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
    utcnow,
)
from .reservation_client import (
    HoldConflict,
    HoldExpired,
    HoldInfo,
    HoldNotFound,
    ReservationClient,
    ReservationRejected,
    ReservationUnavailable,
)

logger = logging.getLogger("payment-service.payment-service")

MONEY = Decimal("0.01")
MAX_AMOUNT = Decimal("99999999.99")


class PaymentServiceError(Exception):
    """Safe, client-facing business error."""

    status_code = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class PaymentValidationError(PaymentServiceError):
    status_code = 422


class PaymentNotFound(PaymentServiceError):
    status_code = 404


class PaymentGone(PaymentServiceError):
    status_code = 410


class PaymentConflict(PaymentServiceError):
    status_code = 409


class PaymentDependencyError(PaymentServiceError):
    status_code = 502


class PaymentUnavailable(PaymentServiceError):
    status_code = 503


@dataclass(frozen=True)
class SimulationOutcome:
    succeeded: bool
    failure_reason: str | None = None


@dataclass(frozen=True)
class ChargeResult:
    payment: Payment
    created: bool


class PaymentSimulator:
    """Deterministic development processor.

    By default every valid payment succeeds. A development client may request
    ``success`` or ``failure`` *only* when ``PAYMENT_SIMULATION_ENABLED=true``.
    Production clients can never force an outcome: the field is rejected when
    the flag is off, and disabling the flag also removes all request control.
    """

    def __init__(self, config: Settings | None = None) -> None:
        self.settings = config or default_settings

    def evaluate(
        self,
        *,
        method: str,
        amount: Decimal,
        requested_outcome: str | None,
    ) -> SimulationOutcome:
        if amount <= 0:
            return SimulationOutcome(False, "No payable amount for this hold.")
        if requested_outcome is not None:
            if not self.settings.payment_simulation_enabled:
                raise PaymentValidationError(
                    "Payment simulation controls are disabled."
                )
            if requested_outcome == "failure":
                return SimulationOutcome(False, "Simulated payment failure.")
            if requested_outcome != "success":
                raise PaymentValidationError("Unsupported simulated outcome.")
        # CARD and WALLET are both accepted in the academic simulation.
        if (method or "").upper() not in {item.value for item in PaymentMethod}:
            return SimulationOutcome(False, "Unsupported payment method.")
        return SimulationOutcome(True, None)


def _normalise_method(value: str) -> str:
    method = (value or "").strip().upper()
    if method not in {item.value for item in PaymentMethod}:
        raise PaymentValidationError("Unsupported payment method. Use CARD or WALLET.")
    return method


def _normalise_currency(value: str | None, config: Settings) -> str:
    currency = (value or config.default_currency).strip().upper()
    if currency not in config.supported_currencies:
        supported = ", ".join(sorted(config.supported_currencies))
        raise PaymentValidationError(f"Unsupported currency. Supported: {supported}.")
    return currency


def _parse_hold_id(value: UUID | str) -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value).strip())
    except (ValueError, AttributeError, TypeError) as exc:
        raise PaymentValidationError("Invalid hold_id; expected a UUID.") from exc


def _money(value: object) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise PaymentDependencyError(
            "The hold total is not a valid payable amount."
        ) from exc
    if not amount.is_finite():
        raise PaymentDependencyError("The hold total is not a valid payable amount.")
    amount = amount.quantize(MONEY, rounding=ROUND_HALF_UP)
    if amount <= 0 or amount > MAX_AMOUNT:
        raise PaymentDependencyError("The hold total is not a valid payable amount.")
    return amount


def _fingerprint(
    *,
    user_id: int,
    hold_id: UUID,
    method: str,
    currency: str,
    simulate_outcome: str | None,
) -> str:
    payload = json.dumps(
        {
            "v": 1,
            "user_id": user_id,
            "hold_id": str(hold_id),
            "method": method,
            "currency": currency,
            "simulate_outcome": simulate_outcome,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _new_transaction_ref() -> str:
    return f"pay_{uuid4().hex}"


class PaymentService:
    def __init__(
        self,
        session_factory: sessionmaker,
        reservation_client: ReservationClient,
        *,
        config: Settings | None = None,
        simulator: PaymentSimulator | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.reservation_client = reservation_client
        self.settings = config or default_settings
        self.simulator = simulator or PaymentSimulator(self.settings)

    # ------------------------------------------------------------------ reads
    def _load(self, payment_id: UUID) -> Payment | None:
        with self.session_factory() as db:
            return db.get(Payment, payment_id)

    def _find_by_key(self, key: str) -> Payment | None:
        with self.session_factory() as db:
            return db.scalar(select(Payment).where(Payment.idempotency_key == key))

    def _find_by_hold(self, hold_id: UUID) -> Payment | None:
        with self.session_factory() as db:
            return db.scalar(select(Payment).where(Payment.hold_id == hold_id))

    def get_payment(
        self,
        payment_id: UUID,
        *,
        user_id: int | None = None,
    ) -> Payment:
        payment = self._load(payment_id)
        if payment is None or (user_id is not None and payment.user_id != user_id):
            # Same response for "missing" and "belongs to somebody else" so the
            # endpoint cannot be used to enumerate other users' payments.
            raise PaymentNotFound("Payment not found.")
        return payment

    def list_payments(
        self,
        *,
        user_id: int | None = None,
        status: str | None = None,
        method: str | None = None,
        currency: str | None = None,
        hold_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Payment], int]:
        conditions = []
        if user_id is not None:
            conditions.append(Payment.user_id == user_id)
        if status:
            conditions.append(Payment.status == status.upper())
        if method:
            conditions.append(Payment.method == method.upper())
        if currency:
            conditions.append(Payment.currency == currency.upper())
        if hold_id is not None:
            conditions.append(Payment.hold_id == hold_id)

        with self.session_factory() as db:
            statement = select(Payment)
            counter = select(func.count()).select_from(Payment)
            if conditions:
                statement = statement.where(*conditions)
                counter = counter.where(*conditions)
            total = int(db.scalar(counter) or 0)
            items = list(
                db.scalars(
                    statement.order_by(Payment.created_at.desc(), Payment.id.desc())
                    .limit(limit)
                    .offset(offset)
                ).all()
            )
        return items, total

    def stats(self) -> dict:
        with self.session_factory() as db:
            by_status = {item.value: 0 for item in PaymentStatus}
            for status_value, count in db.execute(
                select(Payment.status, func.count()).group_by(Payment.status)
            ).all():
                by_status[str(status_value)] = int(count)

            by_method = {
                str(method): int(count)
                for method, count in db.execute(
                    select(Payment.method, func.count()).group_by(Payment.method)
                ).all()
            }
            by_currency = {
                str(currency): int(count)
                for currency, count in db.execute(
                    select(Payment.currency, func.count()).group_by(Payment.currency)
                ).all()
            }

            success_amounts = db.execute(
                select(
                    Payment.status,
                    func.coalesce(func.sum(Payment.amount), 0),
                )
                .where(
                    Payment.status.in_(
                        [PaymentStatus.SUCCEEDED.value, PaymentStatus.REFUNDED.value]
                    )
                )
                .group_by(Payment.status)
            ).all()
            gross = Decimal("0.00")
            refunded = Decimal("0.00")
            for status_value, amount in success_amounts:
                value = Decimal(str(amount or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)
                if status_value == PaymentStatus.REFUNDED.value:
                    refunded += value
                gross += value

            pending_confirmation = int(
                db.scalar(
                    select(func.count()).select_from(Payment).where(
                        Payment.status == PaymentStatus.SUCCEEDED.value,
                        Payment.confirmation_status == ConfirmationStatus.PENDING.value,
                    )
                )
                or 0
            )
            total = int(db.scalar(select(func.count()).select_from(Payment)) or 0)

        return {
            "total_payments": total,
            "by_status": by_status,
            "by_method": by_method,
            "by_currency": by_currency,
            "succeeded_count": by_status.get(PaymentStatus.SUCCEEDED.value, 0),
            "failed_count": by_status.get(PaymentStatus.FAILED.value, 0),
            "refunded_count": by_status.get(PaymentStatus.REFUNDED.value, 0),
            "pending_confirmations": pending_confirmation,
            "gross_amount": gross.quantize(MONEY, rounding=ROUND_HALF_UP),
            "refunded_amount": refunded.quantize(MONEY, rounding=ROUND_HALF_UP),
            "net_amount": (gross - refunded).quantize(MONEY, rounding=ROUND_HALF_UP),
        }

    # ------------------------------------------------------------------ create
    async def charge(
        self,
        *,
        user_id: int,
        hold_id: UUID | str,
        token: str,
        method: str,
        currency: str | None = None,
        simulate_outcome: str | None = None,
        idempotency_key: str | None = None,
        replay_existing_hold: bool = False,
    ) -> ChargeResult:
        """Create and process one payment.

        ``replay_existing_hold`` is used by gRPC: the protobuf contract has no
        idempotency key, so the unique hold id is the replay key. REST keeps
        strict idempotency-key semantics and rejects a different key for the
        same hold.
        """
        if user_id <= 0:
            raise PaymentValidationError("Invalid authenticated user.")
        if not token:
            raise PaymentValidationError("Missing authentication token.")

        method = _normalise_method(method)
        currency = _normalise_currency(currency, self.settings)
        hold_uuid = _parse_hold_id(hold_id)

        requested = (simulate_outcome or "").strip().lower() or None
        if requested is not None and not self.settings.payment_simulation_enabled:
            raise PaymentValidationError("Payment simulation controls are disabled.")
        if requested not in (None, "success", "failure"):
            raise PaymentValidationError("Unsupported simulated outcome.")

        key = idempotency_key.strip() if idempotency_key else None
        if key is not None and not (0 < len(key) <= 128):
            raise PaymentValidationError(
                "Idempotency-Key must be between 1 and 128 characters."
            )

        fingerprint = _fingerprint(
            user_id=user_id,
            hold_id=hold_uuid,
            method=method,
            currency=currency,
            simulate_outcome=requested,
        )

        # Fast path: an earlier request with this key already owns the work.
        if key:
            existing = self._find_by_key(key)
            if existing is not None:
                return await self._replay(existing, fingerprint, user_id)

        existing_hold = self._find_by_hold(hold_uuid)
        if existing_hold is not None:
            return await self._existing_hold_result(
                existing_hold,
                fingerprint=fingerprint,
                user_id=user_id,
                key=key,
                replay_existing_hold=replay_existing_hold,
            )

        # Network call without any open session/transaction.
        try:
            hold = await self.reservation_client.get_hold(hold_uuid, token)
        except HoldNotFound as exc:
            raise PaymentNotFound("Hold not found.") from exc
        except HoldExpired as exc:
            raise PaymentGone("This hold has expired.") from exc
        except HoldConflict as exc:
            raise PaymentConflict("This hold can no longer be used.") from exc
        except (ReservationUnavailable, ReservationRejected) as exc:
            logger.warning("could not load hold %s: %s", hold_uuid, exc)
            raise PaymentUnavailable(
                "The reservation service is temporarily unavailable."
            ) from exc

        # Re-check after the network call: another request may have completed
        # while this one was waiting. Its payment row (or the hold's converted
        # status) must win, not a stale pre-network snapshot.
        if key:
            existing = self._find_by_key(key)
            if existing is not None:
                return await self._replay(existing, fingerprint, user_id)
        existing_hold = self._find_by_hold(hold_uuid)
        if existing_hold is not None:
            return await self._existing_hold_result(
                existing_hold,
                fingerprint=fingerprint,
                user_id=user_id,
                key=key,
                replay_existing_hold=replay_existing_hold,
            )

        self._validate_hold(hold, user_id)
        amount = _money(hold.total)

        outcome = self._create_attempt(
            user_id=user_id,
            hold_uuid=hold_uuid,
            amount=amount,
            currency=currency,
            method=method,
            key=key,
            fingerprint=fingerprint,
        )
        if not outcome.created:
            assert outcome.existing is not None
            return await self._existing_hold_result(
                outcome.existing,
                fingerprint=fingerprint,
                user_id=user_id,
                key=key,
                replay_existing_hold=replay_existing_hold,
            )

        payment_id = outcome.payment_id
        assert payment_id is not None

        # PENDING -> PROCESSING is a short database-only step.
        self._mark_processing(payment_id)

        simulation = self.simulator.evaluate(
            method=method, amount=amount, requested_outcome=requested
        )
        payment = self._finalise(payment_id, simulation)

        if payment.status == PaymentStatus.SUCCEEDED.value:
            # Separate network call after the status commit. A failure here
            # never reverses the charge and never triggers a second charge.
            await self._attempt_confirmation(payment_id, token, raise_on_transient=False)

        final = self._load(payment_id)
        if final is None:  # pragma: no cover - only if the row vanished
            raise PaymentDependencyError("The payment could not be loaded.")
        return ChargeResult(final, True)

    # --------------------------------------------------------------- confirm
    async def retry_confirmation(
        self, payment_id: UUID, *, user_id: int, token: str
    ) -> Payment:
        payment = self.get_payment(payment_id, user_id=user_id)
        if payment.status != PaymentStatus.SUCCEEDED.value:
            raise PaymentConflict(
                "Only a successfully charged payment can confirm a reservation."
            )
        if payment.confirmation_status == ConfirmationStatus.CONFIRMED.value:
            return payment
        if not payment.transaction_ref:
            raise PaymentConflict("This payment has no transaction reference.")

        await self._attempt_confirmation(payment_id, token, raise_on_transient=True)
        refreshed = self._load(payment_id)
        if refreshed is None:  # pragma: no cover
            raise PaymentNotFound("Payment not found.")
        return refreshed

    # --------------------------------------------------------------- refunds
    def refund(self, payment_id: UUID) -> Payment:
        """Simulate a full refund. Idempotent for already-refunded payments."""
        with self.session_factory() as db:
            payment = db.scalar(
                select(Payment).where(Payment.id == payment_id).with_for_update()
            )
            if payment is None:
                raise PaymentNotFound("Payment not found.")
            if payment.status == PaymentStatus.REFUNDED.value:
                return payment
            if payment.status != PaymentStatus.SUCCEEDED.value:
                raise PaymentConflict("Only a successful payment can be refunded.")
            payment.status = PaymentStatus.REFUND_PENDING.value
            db.commit()

        # The simulated refund provider is deterministic and local. No network
        # call and no external transaction are performed here.
        with self.session_factory() as db:
            payment = db.get(Payment, payment_id)
            if payment is None:  # pragma: no cover
                raise PaymentNotFound("Payment not found.")
            if payment.status == PaymentStatus.REFUND_PENDING.value:
                payment.status = PaymentStatus.REFUNDED.value
                payment.refunded_at = utcnow()
                db.commit()
            return payment

    # ------------------------------------------------------------- internals
    @staticmethod
    def _validate_hold(hold: HoldInfo, user_id: int) -> None:
        if hold.user_id != user_id:
            # Do not reveal that somebody else's hold exists.
            raise PaymentNotFound("Hold not found.")
        status = (hold.status or "").lower()
        if status == "expired":
            raise PaymentGone("This hold has expired.")
        if status != "active":
            raise PaymentConflict("This hold is no longer active.")
        if hold.expires_at is not None and _aware(hold.expires_at) <= utcnow():
            raise PaymentGone("This hold has expired.")
        if hold.seconds_left is not None and hold.seconds_left <= 0:
            raise PaymentGone("This hold has expired.")

    @dataclass(frozen=True)
    class _CreateOutcome:
        created: bool
        payment_id: UUID | None = None
        existing: Payment | None = None

    def _create_attempt(
        self,
        *,
        user_id: int,
        hold_uuid: UUID,
        amount: Decimal,
        currency: str,
        method: str,
        key: str | None,
        fingerprint: str,
    ) -> "PaymentService._CreateOutcome":
        """Insert the payment claim atomically.

        The unique indexes on ``idempotency_key`` and ``hold_id`` are the
        concurrency guard. A losing request receives the winning row and
        decides whether it is a replay or a conflict.
        """
        payment_id = uuid4()
        try:
            with self.session_factory() as db:
                if key:
                    duplicate = db.scalar(
                        select(Payment).where(Payment.idempotency_key == key)
                    )
                    if duplicate is not None:
                        return self._CreateOutcome(False, existing=duplicate)
                duplicate_hold = db.scalar(
                    select(Payment).where(Payment.hold_id == hold_uuid)
                )
                if duplicate_hold is not None:
                    return self._CreateOutcome(False, existing=duplicate_hold)

                db.add(
                    Payment(
                        id=payment_id,
                        user_id=user_id,
                        hold_id=hold_uuid,
                        amount=amount,
                        currency=currency,
                        method=method,
                        status=PaymentStatus.PENDING.value,
                        transaction_ref=None,
                        idempotency_key=key,
                        request_fingerprint=fingerprint,
                        confirmation_status=ConfirmationStatus.NOT_REQUIRED.value,
                    )
                )
                db.commit()
            return self._CreateOutcome(True, payment_id=payment_id)
        except IntegrityError:
            # A concurrent request won the unique-key race.
            duplicate = self._find_by_key(key) if key else None
            if duplicate is None:
                duplicate = self._find_by_hold(hold_uuid)
            if duplicate is not None:
                return self._CreateOutcome(False, existing=duplicate)
            raise

    def _mark_processing(self, payment_id: UUID) -> None:
        with self.session_factory() as db:
            payment = db.get(Payment, payment_id)
            if payment is not None and payment.status == PaymentStatus.PENDING.value:
                payment.status = PaymentStatus.PROCESSING.value
                db.commit()

    def _finalise(
        self, payment_id: UUID, simulation: SimulationOutcome
    ) -> Payment:
        with self.session_factory() as db:
            payment = db.get(Payment, payment_id)
            if payment is None:  # pragma: no cover
                raise PaymentDependencyError("The payment could not be loaded.")
            if payment.status not in IN_PROGRESS_STATUSES:
                return payment
            if simulation.succeeded:
                payment.status = PaymentStatus.SUCCEEDED.value
                payment.transaction_ref = _new_transaction_ref()
                payment.failure_reason = None
                payment.confirmation_status = ConfirmationStatus.PENDING.value
            else:
                payment.status = PaymentStatus.FAILED.value
                payment.failure_reason = (
                    simulation.failure_reason or "The simulated payment failed."
                )
                payment.confirmation_status = ConfirmationStatus.NOT_REQUIRED.value
            payment.processed_at = utcnow()
            db.commit()
            return payment

    async def _attempt_confirmation(
        self, payment_id: UUID, token: str, *, raise_on_transient: bool
    ) -> None:
        payment = self._load(payment_id)
        if payment is None or payment.status != PaymentStatus.SUCCEEDED.value:
            return
        if not payment.transaction_ref:
            return

        try:
            await self.reservation_client.confirm_hold(
                payment.hold_id, payment.transaction_ref, token
            )
        except (ReservationUnavailable, ReservationRejected) as exc:
            logger.warning(
                "reservation confirmation temporarily failed for payment %s: %s",
                payment_id,
                exc,
            )
            self._set_confirmation(
                payment_id,
                ConfirmationStatus.PENDING.value,
                "Reservation confirmation is pending; it can be retried.",
            )
            if raise_on_transient:
                raise PaymentUnavailable(
                    "The reservation service is temporarily unavailable; "
                    "the payment is kept and confirmation can be retried."
                ) from exc
            return
        except (HoldNotFound, HoldExpired, HoldConflict) as exc:
            logger.warning(
                "reservation confirmation rejected for payment %s: %s", payment_id, exc
            )
            self._set_confirmation(
                payment_id, ConfirmationStatus.FAILED.value, str(exc)
            )
            return
        except Exception as exc:  # noqa: BLE001 - the charge must stay successful
            logger.exception(
                "unexpected reservation confirmation error for payment %s", payment_id
            )
            self._set_confirmation(
                payment_id,
                ConfirmationStatus.PENDING.value,
                "Reservation confirmation is pending; it can be retried.",
            )
            if raise_on_transient:
                raise PaymentUnavailable(
                    "Reservation confirmation failed; the payment is kept and "
                    "confirmation can be retried."
                ) from exc
            return

        self._set_confirmation(payment_id, ConfirmationStatus.CONFIRMED.value, None)

    def _set_confirmation(
        self, payment_id: UUID, status_value: str, error: str | None
    ) -> None:
        with self.session_factory() as db:
            payment = db.get(Payment, payment_id)
            if payment is None:
                return
            payment.confirmation_status = status_value
            payment.confirmation_error = error
            payment.confirmation_attempted_at = utcnow()
            db.commit()

    async def _replay(
        self, payment: Payment, fingerprint: str, user_id: int
    ) -> ChargeResult:
        if payment.user_id != user_id or payment.request_fingerprint != fingerprint:
            raise PaymentConflict(
                "This Idempotency-Key was already used for a different request."
            )
        if payment.status in IN_PROGRESS_STATUSES:
            refreshed = await self._wait_for_terminal(payment.id)
            if refreshed is None:
                raise PaymentConflict(
                    "A payment with this Idempotency-Key is still being processed. "
                    "Retry shortly."
                )
            payment = refreshed
        return ChargeResult(payment, False)

    async def _existing_hold_result(
        self,
        payment: Payment,
        *,
        fingerprint: str,
        user_id: int,
        key: str | None,
        replay_existing_hold: bool,
    ) -> ChargeResult:
        if payment.user_id != user_id:
            raise PaymentConflict("A payment already exists for this hold.")

        if key and payment.idempotency_key == key:
            return await self._replay(payment, fingerprint, user_id)

        if replay_existing_hold and key is None:
            # gRPC has no idempotency key: the hold id is the replay key.
            if payment.status in IN_PROGRESS_STATUSES:
                refreshed = await self._wait_for_terminal(payment.id)
                if refreshed is None:
                    raise PaymentConflict(
                        "A payment for this hold is still being processed. "
                        "Retry shortly."
                    )
                payment = refreshed
            return ChargeResult(payment, False)

        raise PaymentConflict("A payment already exists for this hold.")

    async def _wait_for_terminal(self, payment_id: UUID) -> Payment | None:
        """Wait for the competing request to reach a terminal status.

        Returns ``None`` when it is still in flight at the deadline so the
        caller can answer 409 and the client can retry the same idempotency
        key later instead of receiving a half-processed payment.
        """
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(0.0, self.settings.idempotency_wait_seconds)
        delay = max(0.01, self.settings.idempotency_poll_seconds)
        while loop.time() < deadline:
            await asyncio.sleep(delay)
            current = self._load(payment_id)
            if current is not None and current.status not in IN_PROGRESS_STATUSES:
                return current
        return None
