"""SQLAlchemy models owned by the Movie Service (movies_db)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .timeutils import utcnow


def _key(values: list[str] | None) -> str:
    """Build the "|a|b|" lookup key used for case-insensitive tag filtering."""
    if not values:
        return "|"
    return "|" + "|".join(str(value).strip().lower() for value in values) + "|"


class Cinema(Base):
    __tablename__ = "cinemas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    city: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    address: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    halls: Mapped[list[Hall]] = relationship(
        back_populates="cinema", cascade="all, delete-orphan", order_by="Hall.id"
    )


class Hall(Base):
    __tablename__ = "halls"
    __table_args__ = (UniqueConstraint("cinema_id", "name", name="uq_hall_cinema_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cinema_id: Mapped[int] = mapped_column(ForeignKey("cinemas.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    screen_type: Mapped[str] = mapped_column(String(20), default="standard", nullable=False)
    rows: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    seats_per_row: Mapped[int] = mapped_column(Integer, default=14, nullable=False)
    aisle_after: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    broken_seats: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    cinema: Mapped[Cinema] = relationship(back_populates="halls")
    showtimes: Mapped[list[Showtime]] = relationship(back_populates="hall", cascade="all, delete-orphan")

    @property
    def total_seats(self) -> int:
        return self.rows * self.seats_per_row - len(self.broken_seats or [])


class Movie(Base):
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    original_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    release_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    director: Mapped[str | None] = mapped_column(String(160), nullable=True)
    cast: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    genres: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    moods: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    genres_key: Mapped[str] = mapped_column(String(400), default="|", nullable=False)
    moods_key: Mapped[str] = mapped_column(String(400), default="|", nullable=False)
    synopsis: Mapped[str] = mapped_column(Text, default="", nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    rating: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    age_rating: Mapped[str] = mapped_column(String(20), default="All ages", nullable=False)
    language: Mapped[str] = mapped_column(String(40), default="English", nullable=False)
    country: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    poster_path: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_now_showing: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    showtimes: Mapped[list[Showtime]] = relationship(back_populates="movie", cascade="all, delete-orphan")

    def sync_keys(self) -> None:
        self.genres_key = _key(self.genres)
        self.moods_key = _key(self.moods)

    @property
    def poster_url(self) -> str:
        """Stable poster URL served by this service (falls back to a generated SVG)."""
        return f"/media/posters/{self.slug}.jpg"


class Showtime(Base):
    __tablename__ = "showtimes"
    __table_args__ = (
        UniqueConstraint("movie_id", "hall_id", "starts_at", name="uq_showtime_movie_hall_start"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), index=True, nullable=False)
    hall_id: Mapped[int] = mapped_column(ForeignKey("halls.id", ondelete="CASCADE"), index=True, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, default=5000, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="MAD", nullable=False)
    language: Mapped[str] = mapped_column(String(20), default="VO", nullable=False)
    format: Mapped[str] = mapped_column(String(20), default="2D", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    movie: Mapped[Movie] = relationship(back_populates="showtimes")
    hall: Mapped[Hall] = relationship(back_populates="showtimes")
