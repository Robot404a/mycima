"""JSON logging and request-log middleware shared by every MyCima service."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

_EXTRA_FIELDS = (
    "event",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "request_id",
    "client",
    "user_id",
)


class JsonFormatter(logging.Formatter):
    """One JSON object per log line, with the service name attached."""

    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in _EXTRA_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(service: str, level: str | None = None) -> logging.Logger:
    """Return a service logger that writes JSON lines to stdout."""
    logger = logging.getLogger(service)
    logger.setLevel((level or os.getenv("LOG_LEVEL", "INFO")).upper())

    already_configured = any(getattr(handler, "_mycima", False) for handler in logger.handlers)
    if not already_configured:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter(service))
        handler._mycima = True  # type: ignore[attr-defined]
        logger.addHandler(handler)

    logger.propagate = False
    return logger


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Log every request with a correlation id, and echo the id back."""

    def __init__(self, app: ASGIApp, service: str, logger: logging.Logger | None = None) -> None:
        super().__init__(app)
        self.service = service
        self.logger = logger or configure_logging(service)

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        started = time.perf_counter()
        client = request.client.host if request.client else "unknown"

        try:
            response = await call_next(request)
        except Exception:
            self.logger.exception(
                "unhandled error",
                extra={
                    "event": "request.error",
                    "method": request.method,
                    "path": request.url.path,
                    "request_id": request_id,
                    "client": client,
                },
            )
            raise

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        self.logger.info(
            "request",
            extra={
                "event": "request.completed",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "request_id": request_id,
                "client": client,
            },
        )
        return response
