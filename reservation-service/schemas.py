import re
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

SEAT_RE = re.compile(r"^[A-Z]{1,2}[0-9]{1,3}$")


class HoldCreate(BaseModel):
    showtime_id: int = Field(gt=0)
    seats: list[str] = Field(min_length=1)

    @field_validator("seats")
    @classmethod
    def clean_seats(cls, value: list[str]) -> list[str]:
        cleaned = [s.strip().upper() for s in value]
        bad = [s for s in cleaned if not SEAT_RE.match(s)]
        if bad:
            raise ValueError(f"Invalid seat label(s): {', '.join(bad)} (expected e.g. 'A5')")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("Duplicate seats in the request.")
        return cleaned


class ConfirmRequest(BaseModel):
    payment_ref: str | None = Field(default=None, max_length=100)


class BookingCreate(ConfirmRequest):
    hold_id: UUID
