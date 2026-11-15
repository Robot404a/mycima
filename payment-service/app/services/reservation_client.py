"""Async HTTP client for the Reservation Service.

Only two endpoints are used, matching the reservation service implemented in
this repository:

* ``GET  /holds/{hold_id}``
* ``POST /holds/{hold_id}/confirm`` with ``{"payment_ref": ...}``

The client always forwards the user's bearer token. The Reservation Service is
responsible for checking ownership and expiry; this service checks both again
before charging, because money must never depend on a single validation layer.
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field

from ..config import settings

logger = logging.getLogger("payment-service.reservation-client")


class ReservationError(Exception):
    """Base class for errors talking to the Reservation Service."""


class ReservationUnavailable(ReservationError):
    """The service could not be reached or returned a server error."""


class ReservationRejected(ReservationError):
    """The service rejected our request (bad credentials/configuration)."""


class HoldNotFound(ReservationError):
    """The hold does not exist or does not belong to the caller."""


class HoldExpired(ReservationError):
    """The hold has expired and can no longer become a booking."""


class HoldConflict(ReservationError):
    """The hold is released or otherwise cannot be confirmed."""


class HoldInfo(BaseModel):
    """The subset of the reservation hold response used for payment."""

    model_config = ConfigDict(extra="ignore")

    id: UUID
    user_id: int
    showtime_id: int | None = None
    status: str
    seats: list[str] = Field(default_factory=list)
    total: Decimal
    expires_at: datetime | None = None
    seconds_left: int | None = None


def _safe_error(response: httpx.Response) -> str:
    # Never propagate raw upstream bodies to clients. Return a useful category
    # for logs only.
    return f"reservation service returned HTTP {response.status_code}"


class ReservationClient:
    """Small, dependency-injectable HTTP client."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout_seconds: float | None = None,
        connect_timeout_seconds: float | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = (base_url or settings.reservation_service_url).rstrip("/")
        self.timeout = float(
            settings.reservation_timeout_seconds
            if timeout_seconds is None
            else timeout_seconds
        )
        self.connect_timeout = float(
            settings.reservation_connect_timeout_seconds
            if connect_timeout_seconds is None
            else connect_timeout_seconds
        )
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout, connect=self.connect_timeout),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    async def _request(
        self,
        method: str,
        path: str,
        token: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        url = f"{self.base_url}{path}"
        try:
            return await self._client.request(
                method, url, headers=self._headers(token), json=json
            )
        except httpx.TimeoutException as exc:
            logger.warning("reservation request timed out: %s %s", method, path)
            raise ReservationUnavailable("The reservation service timed out.") from exc
        except httpx.HTTPError as exc:
            logger.warning("reservation request failed: %s %s (%s)", method, path, exc)
            raise ReservationUnavailable(
                "The reservation service is temporarily unavailable."
            ) from exc

    async def get_hold(self, hold_id: UUID | str, token: str) -> HoldInfo:
        response = await self._request("GET", f"/holds/{hold_id}", token)
        if response.status_code == 200:
            try:
                return HoldInfo.model_validate(response.json())
            except Exception as exc:  # noqa: BLE001 - malformed upstream payload
                logger.error("invalid hold payload from reservation service")
                raise ReservationRejected(
                    "The reservation service returned an invalid response."
                ) from exc

        if response.status_code == 404:
            raise HoldNotFound("Hold not found.")
        if response.status_code == 410:
            raise HoldExpired("This hold has expired.")
        if response.status_code == 409:
            raise HoldConflict("This hold can no longer be used.")
        if response.status_code in (401, 403):
            logger.error("reservation service rejected our JWT (%s)", response.status_code)
            raise ReservationRejected(
                "The reservation service rejected the authentication token."
            )
        if response.status_code >= 500:
            logger.warning("reservation service unavailable: %s", _safe_error(response))
            raise ReservationUnavailable(
                "The reservation service is temporarily unavailable."
            )
        logger.warning("unexpected reservation response: %s", _safe_error(response))
        raise ReservationRejected("The reservation service rejected the request.")

    async def confirm_hold(
        self, hold_id: UUID | str, payment_ref: str, token: str
    ) -> dict[str, Any]:
        response = await self._request(
            "POST",
            f"/holds/{hold_id}/confirm",
            token,
            json={"payment_ref": payment_ref},
        )
        if response.status_code in (200, 201):
            try:
                payload = response.json()
                return payload if isinstance(payload, dict) else {}
            except ValueError:
                return {}

        if response.status_code == 404:
            raise HoldNotFound("Hold not found.")
        if response.status_code == 410:
            raise HoldExpired("This hold has expired.")
        if response.status_code == 409:
            raise HoldConflict("This hold can no longer be confirmed.")
        if response.status_code in (401, 403):
            logger.error("reservation confirm rejected our JWT (%s)", response.status_code)
            raise ReservationRejected(
                "The reservation service rejected the authentication token."
            )
        if response.status_code >= 500:
            logger.warning("reservation confirm unavailable: %s", _safe_error(response))
            raise ReservationUnavailable(
                "The reservation service is temporarily unavailable."
            )
        logger.warning("unexpected reservation confirm response: %s", _safe_error(response))
        raise ReservationRejected("The reservation service rejected the request.")
