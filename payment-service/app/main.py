"""FastAPI application entry point for the MyCima payment service.

One process exposes two transports over the same business logic:

* REST on port 8000 (``REST_PORT``)
* gRPC ``nocturne.payment.PaymentService`` on port 50051 (``GRPC_PORT``)
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from .config import settings
from .database import SessionLocal, engine, init_db, ping_database
from .grpc_server import GrpcServer
from .routers import admin, payments
from .services.payment_service import PaymentService, PaymentServiceError
from .services.reservation_client import ReservationClient, ReservationError
from shared.logging_config import RequestLogMiddleware, configure_logging

logger = configure_logging(settings.service_name, settings.log_level)
log = logging.getLogger("payment-service.main")


async def _prepare_database() -> bool:
    attempts = max(1, settings.database_connect_attempts)
    delay = max(0.0, settings.database_connect_delay_seconds)
    for attempt in range(1, attempts + 1):
        try:
            await asyncio.to_thread(init_db)
            log.info("payment database schema is ready")
            return True
        except Exception as exc:  # noqa: BLE001 - retry while PostgreSQL starts
            log.warning(
                "database not ready (%s/%s): %s", attempt, attempts, exc
            )
            if attempt < attempts:
                await asyncio.sleep(delay)
    log.error("could not create the payment schema; /health will report degraded")
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _prepare_database()

    reservation_client = ReservationClient()
    payment_service = PaymentService(
        SessionLocal, reservation_client, config=settings
    )
    app.state.reservation_client = reservation_client
    app.state.payment_service = payment_service
    app.state.grpc_server = None
    app.state.grpc_enabled = settings.grpc_enabled

    if settings.grpc_enabled:
        grpc_server = GrpcServer(payment_service, config=settings)
        await grpc_server.start()
        app.state.grpc_server = grpc_server
    else:
        log.info("gRPC server disabled by configuration")

    log.info("starting", extra={"event": "service.start"})
    try:
        yield
    finally:
        if app.state.grpc_server is not None:
            await app.state.grpc_server.stop()
        await reservation_client.aclose()
        engine.dispose()
        log.info("stopped", extra={"event": "service.stop"})


app = FastAPI(
    title="MyCima Payment Service",
    description=(
        "Simulated payment processing for MyCima reservation holds. "
        "Amounts are always retrieved from the Reservation Service."
    ),
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(RequestLogMiddleware, service=settings.service_name, logger=logger)

app.include_router(payments.router)
app.include_router(admin.router)


@app.exception_handler(PaymentServiceError)
async def payment_service_error_handler(
    request: Request, exc: PaymentServiceError
) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(OperationalError)
async def database_unavailable_handler(
    request: Request, exc: OperationalError
) -> JSONResponse:
    log.error("database unavailable: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Database temporarily unavailable."},
    )


@app.exception_handler(ReservationError)
async def reservation_error_handler(
    request: Request, exc: ReservationError
) -> JSONResponse:
    log.warning("reservation dependency error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "The reservation service is temporarily unavailable."},
    )


@app.get("/", tags=["meta"], summary="Service banner")
def root() -> dict:
    return {
        "service": settings.service_name,
        "docs": "/docs",
        "health": "/health",
        "rest": "/payments",
        "grpc": f"{settings.grpc_host}:{settings.grpc_port}",
    }


@app.get("/health", tags=["meta"], summary="Health check")
def health() -> JSONResponse:
    database_ok = ping_database()
    grpc_server = getattr(app.state, "grpc_server", None)
    if not settings.grpc_enabled:
        grpc_state = "disabled"
    elif grpc_server is not None and getattr(grpc_server, "running", False):
        grpc_state = "up"
    else:
        grpc_state = "down"

    healthy = database_ok and grpc_state in {"up", "disabled"}
    body = {
        "status": "ok" if healthy else "degraded",
        "service": settings.service_name,
        "database": "up" if database_ok else "down",
        "grpc": grpc_state,
    }
    return JSONResponse(
        status_code=(
            status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
        ),
        content=body,
    )
