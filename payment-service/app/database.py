"""Database engine, session factory and schema creation for the payment service.

The service owns exactly one database. It never opens a connection to the
user, reservation or movie databases.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


def _normalise_url(url: str) -> str:
    """Use the psycopg 3 SQLAlchemy dialect for plain ``postgresql://`` URLs."""
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    return url


DATABASE_URL = _normalise_url(settings.database_url)
_IS_SQLITE = DATABASE_URL.startswith("sqlite")

_connect_args: dict[str, object] = {}
if _IS_SQLITE:
    # Tests and optional local runs use a file-based SQLite database. Disabling
    # the thread check lets FastAPI's worker threads and gRPC share the engine.
    _connect_args = {"check_same_thread": False, "timeout": 30}

engine = create_engine(
    DATABASE_URL,
    future=True,
    pool_pre_ping=not _IS_SQLITE,
    connect_args=_connect_args,
)

if _IS_SQLITE:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # pragma: no cover - setup
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA journal_mode=WAL")
        finally:
            cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


class Base(DeclarativeBase):
    """Declarative base for tables owned by the payment service."""


def get_db() -> Iterator[Session]:
    """FastAPI dependency for read-only endpoints."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create the payment tables if they do not exist yet."""
    from . import models  # noqa: F401 - register mappings before create_all

    Base.metadata.create_all(bind=engine)


def ping_database() -> bool:
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        return True
    except Exception:  # noqa: BLE001 - health checks must never raise
        return False
