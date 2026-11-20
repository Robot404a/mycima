"""Database engine and session management for the Movie Service."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

_connect_args = {}
if settings.database_url.startswith("sqlite"):
    _connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    future=True,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


class Base(DeclarativeBase):
    """Declarative base for every table owned by the movie service."""


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "cinemas": {
        "description": "VARCHAR(500)",
        "amenities": "JSON",
    },
    "halls": {
        "supported_formats": "JSON",
        "seat_categories": "JSON",
        "description": "VARCHAR(500)",
        "is_active": "BOOLEAN DEFAULT TRUE NOT NULL",
    },
    "movies": {
        "tagline": "VARCHAR(255)",
        "release_date": "DATE",
        "backdrop_url": "VARCHAR(500)",
        "trailer_url": "VARCHAR(500)",
        "status": "VARCHAR(20) DEFAULT 'now_showing' NOT NULL",
        "featured": "BOOLEAN DEFAULT FALSE NOT NULL",
    },
    "showtimes": {
        "format_locked": "BOOLEAN DEFAULT FALSE NOT NULL",
        "is_active": "BOOLEAN DEFAULT TRUE NOT NULL",
    },
}


def _ensure_columns() -> None:
    """create_all() only creates tables — add columns introduced after it first ran."""
    tables = set(inspect(engine).get_table_names())
    for table, columns in _ADDED_COLUMNS.items():
        if table not in tables:
            continue
        existing = {column["name"] for column in inspect(engine).get_columns(table)}
        missing = {name: ddl for name, ddl in columns.items() if name not in existing}
        if not missing:
            continue
        with engine.begin() as conn:
            for name, ddl in missing.items():
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))

    # Older rows predate the status column: derive it from the public flag.
    with engine.begin() as conn:
        if "movies" in tables:
            conn.execute(
                text(
                    "UPDATE movies SET status = CASE WHEN is_now_showing THEN 'now_showing' "
                    "ELSE 'coming_soon' END WHERE status IS NULL"
                )
            )


def _backfill_hall_formats() -> None:
    """Give existing halls their equipment list so format rules can apply."""
    from .formats import default_supported_formats
    from .models import Hall

    with SessionLocal() as db:
        changed = False
        for hall in db.query(Hall).all():
            payload = {"supported_formats": default_supported_formats(hall.screen_type)}
            if not hall.supported_formats:
                hall.supported_formats = payload["supported_formats"]
                changed = True
            if hall.seat_categories is None:
                hall.seat_categories = {}
                changed = True
        if changed:
            db.commit()


def init_db() -> None:
    from . import models  # noqa: F401  (register the mappings before creating tables)

    Base.metadata.create_all(bind=engine)
    _ensure_columns()
    _backfill_hall_formats()
