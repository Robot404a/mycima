"""MyCima user service: registration, login and profile management."""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from sqlalchemy import select, text

from config import settings
from database import Base, SessionLocal, engine
from models import User
from routers import admin, auth, users
from shared.auth import hash_password
from shared.logging_config import RequestLogMiddleware, configure_logging

SERVICE = settings.service_name
logger = configure_logging(SERVICE)


async def initialise_database(max_attempts: int = 15, delay_seconds: float = 2.0) -> None:
    """Create tables, retrying while PostgreSQL is still starting."""
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            Base.metadata.create_all(bind=engine)
            return
        except Exception as exc:  # noqa: BLE001 - report any driver error
            last_error = exc
            logger.warning(
                "database not ready (attempt %s/%s): %s", attempt, max_attempts, exc
            )
            await asyncio.sleep(delay_seconds)
    raise RuntimeError("Could not initialise the users database") from last_error


def seed_admin() -> None:
    """Create the demo administrator once, if it is configured and missing."""
    if not settings.admin_email or not settings.admin_password:
        return
    if len(settings.admin_password) < 8:
        logger.warning("ADMIN_PASSWORD is shorter than 8 characters; skipping seed")
        return

    with SessionLocal() as db:
        exists = db.scalar(select(User).where(User.email == settings.admin_email))
        if exists is not None:
            return
        db.add(
            User(
                email=settings.admin_email,
                password_hash=hash_password(settings.admin_password),
                full_name=settings.admin_full_name,
                role="admin",
            )
        )
        db.commit()
        logger.info(
            "seeded administrator account",
            extra={"event": "user.seed", "user_id": settings.admin_email},
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    await initialise_database()
    seed_admin()
    logger.info("starting", extra={"event": "service.start"})
    yield
    logger.info("stopped", extra={"event": "service.stop"})


app = FastAPI(
    title="MyCima User Service",
    description="Accounts, authentication and JWT issuing for MyCima.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(RequestLogMiddleware, service=SERVICE, logger=logger)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(admin.router)


@app.get("/health", tags=["health"])
def health(response: Response) -> dict:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - health must never raise
        response.status_code = 503
        return {
            "status": "degraded",
            "service": SERVICE,
            "database": "down",
            "detail": str(exc),
            "timestamp": time.time(),
        }

    return {
        "status": "ok",
        "service": SERVICE,
        "database": "up",
        "timestamp": time.time(),
    }
