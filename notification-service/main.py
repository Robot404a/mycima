"""Notification service: stores and sends emails for reservation events.

Paths here are WITHOUT the gateway's /api prefix (the gateway strips it).
POST /notifications is internal only: it is called by other services, never through the gateway.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

import psycopg
from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import JSONResponse
from psycopg_pool import PoolTimeout

import config
import db
import service
from auth import USING_SHARED_AUTH, admin_user, current_user, internal_only, user_id_of
from logging_setup import RequestLogMiddleware, configure_logging
from schemas import NotificationCreate, NotificationOut

logger = configure_logging("notification-service")
log = logging.getLogger("notification-service.main")


async def _ensure_schema(attempts: int = 15, delay: float = 2.0) -> bool:
    for attempt in range(1, attempts + 1):
        try:
            await asyncio.to_thread(db.apply_schema)
            log.info("database schema is ready")
            return True
        except Exception as exc:
            log.warning("database not ready yet (%s/%s): %s", attempt, attempts, exc)
            await asyncio.sleep(delay)
    log.error("could not prepare the database schema; will keep retrying in the background")
    return False


async def _retry_loop() -> None:
    """Re-sends failed emails (up to MAX_SEND_ATTEMPTS) even when nobody is calling us."""
    while True:
        await asyncio.sleep(config.RETRY_INTERVAL_SECONDS)
        try:
            if not db.schema_ready:
                await asyncio.to_thread(db.apply_schema)
            processed = await asyncio.to_thread(service.retry_failed)
            if processed:
                log.info("retried %s notification(s)", processed)
        except Exception as exc:  # keep the loop alive
            log.warning("notification retry failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_pool()
    if USING_SHARED_AUTH:
        log.info("authentication: using shared.auth")
    else:
        log.warning("shared/ not found: using the local JWT fallback (JWT_SECRET must match the User service)")
    await _ensure_schema()
    task = asyncio.create_task(_retry_loop())
    yield
    task.cancel()
    db.close_pool()


app = FastAPI(title="Notification Service", lifespan=lifespan)
app.add_middleware(RequestLogMiddleware, service="notification-service", logger=logger)


@app.exception_handler(PoolTimeout)
@app.exception_handler(psycopg.OperationalError)
async def database_down_handler(request: Request, exc: Exception):
    log.error("database unavailable: %s", exc)
    return JSONResponse(status_code=503, content={"detail": "Database temporarily unavailable."})


# --------------------------------------------------------------------------- health
@app.get("/health")
def health():
    if not db.ping():
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "down"})
    if not db.schema_ready:
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "schema_pending"})
    return {"status": "ok", "service": "notification-service", "database": "up"}


# --------------------------------------------------------------------------- internal (service-to-service)
@app.post("/notifications", status_code=201, response_model=NotificationOut,
          dependencies=[Depends(internal_only)])
def create_notification(body: NotificationCreate):
    """Store the notification and try to send it now. If SMTP fails the row is saved as
    'failed' and the retry loop picks it up, so the caller always gets a 201."""
    return service.create_notification(body)


# --------------------------------------------------------------------------- user
@app.get("/notifications")
def my_notifications(status: str | None = Query(None, pattern="^(pending|sent|failed)$"),
                     limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                     user: dict = Depends(current_user)):
    with db.get_conn() as conn:
        return {"notifications": service.list_notifications(
            conn, user_id=user_id_of(user), status=status, limit=limit, offset=offset)}


@app.get("/notifications/{notification_id}", response_model=NotificationOut)
def get_notification(notification_id: int, user: dict = Depends(current_user)):
    with db.get_conn() as conn:
        return service.get_notification(conn, notification_id, user_id_of(user))


# --------------------------------------------------------------------------- admin
@app.get("/admin/notifications")
def admin_notifications(status: str | None = Query(None, pattern="^(pending|sent|failed)$"),
                        user_id: int | None = None,
                        limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                        _: dict = Depends(admin_user)):
    with db.get_conn() as conn:
        return {"notifications": service.list_notifications(
            conn, user_id=user_id, status=status, limit=limit, offset=offset)}


@app.post("/admin/notifications/{notification_id}/retry", response_model=NotificationOut)
def admin_retry_notification(notification_id: int, _: dict = Depends(admin_user)):
    return service.retry_one(notification_id)