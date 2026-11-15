"""Calls the notification service. Never raises: a failed email must not break a booking."""
import json
import logging
from typing import Any

import httpx

import config

log = logging.getLogger("reservation-service.notification")


def send(*, user_id: int, email: str | None, type: str,
         reference_id: str, data: dict[str, Any]) -> bool:
    """Returns True if the notification service accepted it, False otherwise."""
    if not config.NOTIFICATION_ENABLED:
        return False
    if not email:
        log.warning("no email for user %s, skipping %s notification", user_id, type)
        return False
    payload = {
        "user_id": user_id,
        "recipient_email": email,
        "type": type,
        "reference_id": reference_id,
        # Decimal / datetime / UUID values become strings
        "data": json.loads(json.dumps(data, default=str)),
    }
    try:
        resp = httpx.post(
            f"{config.NOTIFICATION_SERVICE_URL}/notifications",
            json=payload,
            headers={"X-Internal-Token": config.INTERNAL_API_KEY},
            timeout=config.NOTIFICATION_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        log.warning("could not send %s notification for %s: %s", type, reference_id, exc)
        return False