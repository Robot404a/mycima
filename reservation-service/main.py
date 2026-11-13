"""Reservation service: seat availability, temporary seat holds, bookings.

Paths here are WITHOUT the gateway's /api prefix (the gateway strips it).
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from psycopg_pool import PoolTimeout

import config
import db
import movie_client
import service
from auth import USING_SHARED_AUTH, admin_user, current_user, optional_user, user_id_of
from logging_setup import RequestLogMiddleware, configure_logging
from schemas import BookingCreate, ConfirmRequest, HoldCreate

logger = configure_logging("reservation-service")
log = logging.getLogger("reservation-service.main")


def _expire_once() -> int:
    with db.get_conn() as conn:
        return service.expire_holds(conn)


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


async def _cleanup_loop() -> None:
    """Frees seats of expired holds even when nobody is booking."""
    while True:
        await asyncio.sleep(config.CLEANUP_INTERVAL_SECONDS)
        try:
            if not db.schema_ready:
                await asyncio.to_thread(db.apply_schema)
            freed = await asyncio.to_thread(_expire_once)
            if freed:
                log.info("expired %s overdue hold(s)", freed)
        except Exception as exc:  # keep the loop alive
            log.warning("hold cleanup failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_pool()
    if USING_SHARED_AUTH:
        log.info("authentication: using shared.auth")
    else:
        log.warning("shared/ not found: using the local JWT fallback (JWT_SECRET must match the User service)")
    await _ensure_schema()
    task = asyncio.create_task(_cleanup_loop())
    yield
    task.cancel()
    db.close_pool()


app = FastAPI(title="Reservation Service", lifespan=lifespan)
app.add_middleware(RequestLogMiddleware, service="reservation-service", logger=logger)


@app.exception_handler(service.SeatsUnavailable)
async def seats_unavailable_handler(request: Request, exc: service.SeatsUnavailable):
    return JSONResponse(
        status_code=409,
        content={"detail": {"message": "Some seats are no longer available.", "unavailable_seats": exc.seats}},
    )


@app.exception_handler(PoolTimeout)
@app.exception_handler(psycopg.OperationalError)
async def database_down_handler(request: Request, exc: Exception):
    log.error("database unavailable: %s", exc)
    return JSONResponse(status_code=503, content={"detail": "Database temporarily unavailable."})


def _ensure_not_started(info: movie_client.ShowtimeInfo) -> None:
    if info.starts_at and info.starts_at <= datetime.now(timezone.utc):
        raise HTTPException(409, "This showtime has already started.")


# --------------------------------------------------------------------------- health
@app.get("/health")
def health():
    if not db.ping():
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "down"})
    if not db.schema_ready:
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "schema_pending"})
    return {"status": "ok", "service": "reservation-service", "database": "up"}


# --------------------------------------------------------------------------- showtimes (public)
@app.get("/showtimes/availability")
def availability_many(ids: str = Query(..., description="Comma-separated showtime ids, e.g. 1,2,3")):
    try:
        showtime_ids = sorted({int(x) for x in ids.split(",") if x.strip()})
    except ValueError:
        raise HTTPException(422, "ids must be comma-separated integers.")
    if not showtime_ids or len(showtime_ids) > 50:
        raise HTTPException(422, "Provide between 1 and 50 showtime ids.")
    infos = [movie_client.get_showtime(sid) for sid in showtime_ids]
    with db.get_conn() as conn:
        counts = service.counts_for(conn, showtime_ids)
    return {"showtimes": [service.availability(info, counts[info.id]) for info in infos]}


@app.get("/showtimes/{showtime_id}/seats")
def seats(showtime_id: int, user: dict | None = Depends(optional_user)):
    info = movie_client.get_showtime(showtime_id)
    uid = user_id_of(user) if user else None
    with db.get_conn() as conn:
        return service.seat_map(conn, info, uid)


@app.get("/showtimes/{showtime_id}/availability")
def availability_one(showtime_id: int):
    info = movie_client.get_showtime(showtime_id)
    with db.get_conn() as conn:
        counts = service.counts_for(conn, [showtime_id])
    return service.availability(info, counts[showtime_id])


@app.get("/showtimes/{showtime_id}/suggest")
def suggest(showtime_id: int, count: int = Query(2, ge=1)):
    if count > config.MAX_SEATS_PER_HOLD:
        raise HTTPException(422, f"You can select at most {config.MAX_SEATS_PER_HOLD} seats.")
    info = movie_client.get_showtime(showtime_id)
    if count > info.seats_per_row:
        raise HTTPException(422, "Not enough seats in a row for that group size.")
    with db.get_conn() as conn:
        unavailable = set(service.taken_seats(conn, showtime_id))
    return {"showtime_id": showtime_id, "count": count,
            "suggestions": service.suggest_seats(info, unavailable, count)}


# --------------------------------------------------------------------------- holds
@app.post("/holds", status_code=201)
def create_hold(body: HoldCreate, user: dict = Depends(current_user)):
    uid = user_id_of(user)
    if len(body.seats) > config.MAX_SEATS_PER_HOLD:
        raise HTTPException(422, f"You can select at most {config.MAX_SEATS_PER_HOLD} seats.")
    info = movie_client.get_showtime(body.showtime_id)
    _ensure_not_started(info)
    with db.get_conn() as conn:
        return service.create_hold(conn, uid, info, body.seats)


@app.get("/holds")
def my_holds(status: str | None = Query("active", pattern="^(active|expired|released|converted)$"),
             user: dict = Depends(current_user)):
    with db.get_conn() as conn:
        return {"holds": service.list_holds(conn, user_id=user_id_of(user), status=status)}


@app.get("/holds/{hold_id}")
def get_hold(hold_id: UUID, user: dict = Depends(current_user)):
    with db.get_conn() as conn:
        return service.get_hold(conn, hold_id, user_id_of(user))


@app.delete("/holds/{hold_id}")
def release_hold(hold_id: UUID, user: dict = Depends(current_user)):
    with db.get_conn() as conn:
        return service.release_hold(conn, user_id_of(user), hold_id)


def _confirm(hold_id: UUID, payment_ref: str | None, user: dict) -> dict:
    with db.get_conn() as conn:
        booking, created = service.confirm_hold(conn, user_id_of(user), hold_id, payment_ref)
    if created:  # after commit, and only the first time
        service.after_booking_confirmed(booking)
    return booking


@app.post("/holds/{hold_id}/confirm", status_code=201)
def confirm_hold(hold_id: UUID, body: ConfirmRequest | None = None, user: dict = Depends(current_user)):
    return _confirm(hold_id, body.payment_ref if body else None, user)


# --------------------------------------------------------------------------- bookings
@app.post("/bookings", status_code=201)
def create_booking(body: BookingCreate, user: dict = Depends(current_user)):
    """Same as POST /holds/{id}/confirm, for clients that prefer creating a booking resource."""
    return _confirm(body.hold_id, body.payment_ref, user)


@app.get("/bookings")
def my_bookings(status: str | None = Query(None, pattern="^(confirmed|cancelled)$"),
                limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                user: dict = Depends(current_user)):
    with db.get_conn() as conn:
        return {"bookings": service.list_bookings(conn, user_id=user_id_of(user), status=status,
                                                  limit=limit, offset=offset)}


@app.get("/bookings/{booking_id}")
def get_booking(booking_id: UUID, user: dict = Depends(current_user)):
    with db.get_conn() as conn:
        return service.get_booking(conn, booking_id, user_id_of(user))


@app.post("/bookings/{booking_id}/cancel")
def cancel_booking(booking_id: UUID, user: dict = Depends(current_user)):
    uid = user_id_of(user)
    with db.get_conn() as conn:
        booking = service.get_booking(conn, booking_id, uid)
        try:
            _ensure_not_started(movie_client.get_showtime(booking["showtime_id"]))
        except HTTPException as exc:
            if exc.status_code == 409:   # showtime started: cannot cancel
                raise
            # Movie service unavailable: do not block the cancellation
        return service.cancel_booking(conn, booking_id, uid)


# --------------------------------------------------------------------------- admin
@app.get("/admin/bookings")
def admin_bookings(status: str | None = Query(None, pattern="^(confirmed|cancelled)$"),
                   showtime_id: int | None = None, user_id: int | None = None,
                   limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                   _: dict = Depends(admin_user)):
    with db.get_conn() as conn:
        return {"bookings": service.list_bookings(conn, user_id=user_id, status=status,
                                                  showtime_id=showtime_id, limit=limit, offset=offset)}


@app.post("/admin/bookings/{booking_id}/cancel")
def admin_cancel_booking(booking_id: UUID, _: dict = Depends(admin_user)):
    with db.get_conn() as conn:
        return service.cancel_booking(conn, booking_id, None)


@app.get("/admin/holds")
def admin_holds(status: str | None = Query("active", pattern="^(active|expired|released|converted)$"),
                showtime_id: int | None = None, user_id: int | None = None,
                limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                _: dict = Depends(admin_user)):
    with db.get_conn() as conn:
        return {"holds": service.list_holds(conn, user_id=user_id, status=status,
                                            showtime_id=showtime_id, limit=limit, offset=offset)}


@app.get("/admin/stats")
def admin_stats(_: dict = Depends(admin_user)):
    with db.get_conn() as conn:
        return service.stats(conn)
