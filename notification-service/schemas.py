"""Request / response models."""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field

NotificationType = Literal["reservation_created", "reservation_cancelled"]
NotificationStatus = Literal["pending", "sent", "failed"]


class NotificationCreate(BaseModel):
    """What reservation-service sends us."""
    user_id: int
    recipient_email: EmailStr
    type: NotificationType
    reference_id: str | None = None          # e.g. the reservation id
    # Values used to fill the email template. Not stored, only the rendered result is.
    # Expected keys: movie_title, showtime, seats (list), total_price
    data: dict[str, Any] = Field(default_factory=dict)


class NotificationOut(BaseModel):
    id: int
    user_id: int
    recipient_email: str
    type: NotificationType
    reference_id: str | None = None
    subject: str
    status: NotificationStatus
    attempts: int
    error: str | None = None
    created_at: datetime
    sent_at: datetime | None = None
    read_at: datetime | None = None