"""Uses the team's shared logging when available, otherwise a small local equivalent."""
import logging
import time
import uuid

try:
    from shared.logging_config import RequestLogMiddleware, configure_logging  # type: ignore
except ImportError:
    from starlette.middleware.base import BaseHTTPMiddleware

    def configure_logging(service: str) -> logging.Logger:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
        return logging.getLogger(service)

    class RequestLogMiddleware(BaseHTTPMiddleware):
        def __init__(self, app, service: str, logger: logging.Logger):
            super().__init__(app)
            self.logger = logger

        async def dispatch(self, request, call_next):
            started = time.perf_counter()
            request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            self.logger.info(
                "%s %s -> %s (%.1f ms) rid=%s",
                request.method, request.url.path, response.status_code,
                (time.perf_counter() - started) * 1000, request_id,
            )
            return response
