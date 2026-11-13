"""Pydantic models: API contracts of the Movie Service (Swagger documentation)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MovieOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    original_title: str | None = None
    release_year: int
    director: str | None = None
    cast: list[str] = []
    genres: list[str] = []
    moods: list[str] = []
    synopsis: str
    duration_minutes: int
    rating: float
    age_rating: str
    language: str
    country: str
    poster_url: str
    is_now_showing: bool


class MovieListOut(BaseModel):
    items: list[MovieOut]
    total: int
    limit: int
    offset: int


class MovieBrief(BaseModel):
    id: int
    slug: str
    title: str
    release_year: int
    duration_minutes: int
    genres: list[str] = []
    poster_url: str


class CinemaBrief(BaseModel):
    id: int
    name: str
    city: str


class CinemaOut(CinemaBrief):
    address: str
    phone: str | None = None


class CinemaListOut(BaseModel):
    items: list[CinemaOut]
    total: int


class HallBrief(BaseModel):
    id: int
    name: str
    screen_type: str
    total_seats: int


class HallOut(HallBrief):
    cinema_id: int
    rows: int
    seats_per_row: int
    aisle_after: list[int] = []
    cinema: CinemaBrief | None = None


class HallListOut(BaseModel):
    items: list[HallOut]
    total: int


class SeatOut(BaseModel):
    id: str
    number: int
    blocked: bool


class SeatRowOut(BaseModel):
    row: str
    seats: list[SeatOut]


class HallLayoutOut(BaseModel):
    hall_id: int
    name: str
    screen_type: str
    rows: int
    seats_per_row: int
    aisle_after: list[int] = []
    row_labels: list[str] = []
    total_seats: int
    cinema: CinemaBrief | None = None
    layout: list[SeatRowOut]


class ShowtimeOut(BaseModel):
    id: int
    movie_id: int
    hall_id: int
    starts_at: str = Field(description="Start time in UTC, ISO 8601")
    price: float = Field(description="Ticket price in the showtime currency")
    price_cents: int
    currency: str
    language: str = Field(description="VO, VF or VOSTFR")
    format: str = Field(description="2D, 3D, IMAX or VIP")
    movie: MovieBrief | None = None
    hall: HallBrief | None = None
    cinema: CinemaBrief | None = None


class ShowtimeListOut(BaseModel):
    items: list[ShowtimeOut]
    total: int


# ---------------------------------------------------------------- admin payloads


class MovieCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=140)
    original_title: str | None = None
    release_year: int = Field(ge=1888, le=2100)
    director: str | None = None
    cast: list[str] = []
    genres: list[str] = []
    moods: list[str] = []
    synopsis: str = ""
    duration_minutes: int = Field(default=100, ge=1, le=400)
    rating: float = Field(default=0.0, ge=0, le=10)
    age_rating: str = "All ages"
    language: str = "English"
    country: str = ""
    poster_path: str | None = None
    is_now_showing: bool = True


class MovieUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    original_title: str | None = None
    release_year: int | None = Field(default=None, ge=1888, le=2100)
    director: str | None = None
    cast: list[str] | None = None
    genres: list[str] | None = None
    moods: list[str] | None = None
    synopsis: str | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=400)
    rating: float | None = Field(default=None, ge=0, le=10)
    age_rating: str | None = None
    language: str | None = None
    country: str | None = None
    poster_path: str | None = None
    is_now_showing: bool | None = None


class ShowtimeCreate(BaseModel):
    movie_id: int
    hall_id: int
    starts_at: datetime = Field(description="ISO 8601 date-time (UTC if no offset is given)")
    price_cents: int | None = Field(default=None, ge=0)
    language: str = "VO"
    format: str | None = None


class HallCreate(BaseModel):
    cinema_id: int
    name: str = Field(min_length=1, max_length=80)
    screen_type: str = Field(default="standard", pattern="^(standard|premium|imax|vip)$")
    rows: int = Field(default=10, ge=1, le=40)
    seats_per_row: int = Field(default=14, ge=1, le=40)
    aisle_after: list[int] = []
    broken_seats: list[str] = []


class CinemaCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    city: str = Field(min_length=1, max_length=80)
    address: str = ""
    phone: str | None = None
