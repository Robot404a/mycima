import asyncio
import os
import socket
import threading
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware

from shared.auth import decode_access_token, user_from_payload
from shared.logging_config import RequestLogMiddleware, configure_logging

SERVICE = "gateway"
logger = configure_logging(SERVICE)

USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user-service:8000").rstrip("/")
MOVIE_SERVICE_URL = os.getenv("MOVIE_SERVICE_URL", "http://movie-service:8000").rstrip("/")
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://notification-service:8000").rstrip("/")
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://ai-assistant-service:8000").rstrip("/")
RESERVATION_SERVICE_URL = os.getenv("RESERVATION_SERVICE_URL", "http://reservation-service:8000").rstrip("/")
GATEWAY_TIMEOUT = float(os.getenv("GATEWAY_TIMEOUT_SECONDS", "15"))
AI_TIMEOUT = float(os.getenv("AI_TIMEOUT_SECONDS", "90"))
CONFIRM_TIMEOUT = float(os.getenv("CONFIRM_TIMEOUT_SECONDS", "60"))
CONNECT_TIMEOUT = float(os.getenv("GATEWAY_CONNECT_TIMEOUT_SECONDS", "3.5"))

PROTECTED_PREFIXES = ("/api/users", "/api/holds", "/api/bookings", "/api/notifications", "/api/assistant")
PUBLIC_MOVIE_PREFIXES = ("/api/movies", "/api/halls", "/api/media", "/media")
HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-length",
    "content-encoding",
}
PASS_RESPONSE_HEADERS = {
    "content-type",
    "cache-control",
    "etag",
    "last-modified",
    "content-disposition",
    "www-authenticate",
    "retry-after",
}


class ReservationBalancer:
    """Round-robin over the A records of the reservation service.

    Docker Compose's internal DNS returns one address per replica. Resolving
    explicitly lets the gateway rotate every request instead of pinning a
    keep-alive connection to a single replica.
    """

    def __init__(self, raw_url: str, extra_urls: str = ""):
        self.raw_url = raw_url
        self.extra_urls = [item.strip().rstrip("/") for item in extra_urls.split(",") if item.strip()]
        self._lock = threading.Lock()
        self._index = 0
        self._targets: list[str] = []
        self._resolved_at = 0.0

    def _resolve(self) -> list[str]:
        if self.extra_urls:
            return self.extra_urls
        parts = urlsplit(self.raw_url)
        host = parts.hostname
        port = parts.port or (443 if parts.scheme == "https" else 80)
        if not host:
            return [self.raw_url]
        prefix = parts.path.rstrip("/")
        try:
            infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except OSError:
            return [self.raw_url]
        targets = []
        seen = set()
        for info in infos:
            address = info[4][0]
            if address in seen:
                continue
            seen.add(address)
            display = f"[{address}]" if ":" in address else address
            targets.append(f"{parts.scheme}://{display}:{port}{prefix}")
        return targets or [self.raw_url]

    def targets(self) -> list[str]:
        with self._lock:
            now = time.monotonic()
            if not self._targets or now - self._resolved_at > 15:
                self._targets = self._resolve()
                self._resolved_at = now
            return list(self._targets)

    def next(self) -> str:
        with self._lock:
            now = time.monotonic()
            if not self._targets or now - self._resolved_at > 15:
                self._targets = self._resolve()
                self._resolved_at = now
            target = self._targets[self._index % len(self._targets)]
            self._index = (self._index + 1) % max(1, len(self._targets))
            return target


reservation_balancer = ReservationBalancer(
    RESERVATION_SERVICE_URL, os.getenv("RESERVATION_SERVICE_URLS", "")
)


class AuthRateLimiter:
    def __init__(self, limit: int, window_seconds: int = 60):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        if self.limit <= 0:
            return True
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] > self.window:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            return True


auth_limiter = AuthRateLimiter(int(os.getenv("AUTH_RATE_LIMIT_PER_MINUTE", "40")))


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def require_user(request: Request) -> dict | None:
    authorization = request.headers.get("authorization")
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    try:
        return user_from_payload(decode_access_token(token.strip()))
    except HTTPException:
        return None


def route_backend(path: str, method: str) -> tuple[str, str] | None:
    """Return (service, upstream path) for an API path."""
    if path == "/api" or path == "/api/":
        return None
    upstream = path[4:] if path.startswith("/api") else path
    if not upstream.startswith("/"):
        upstream = "/" + upstream

    if upstream == "/health":
        return None

    if upstream.startswith("/auth/") or upstream == "/auth":
        return "user", upstream
    if upstream.startswith("/users"):
        return "user", upstream

    if upstream.startswith("/admin/"):
        section = upstream.split("/")[2] if len(upstream.split("/")) > 2 else ""
        if section == "users":
            return "user", upstream
        if section in {"movies", "cinemas", "halls", "showtimes"}:
            return "movie", upstream
        if section in {"bookings", "holds", "stats"}:
            return "reservation", upstream
        if section == "notifications":
            return "notification", upstream
        return None

    if upstream.startswith("/movies") or upstream.startswith("/halls") or upstream.startswith("/media") or upstream.startswith("/cinemas"):
        return "movie", upstream

    if upstream.startswith("/showtimes"):
        parts = upstream.strip("/").split("/")
        if upstream == "/showtimes/availability":
            return "reservation", upstream
        if len(parts) >= 3 and parts[2] in {"seats", "suggest", "availability"}:
            return "reservation", upstream
        return "movie", upstream

    if upstream.startswith("/holds") or upstream.startswith("/bookings"):
        return "reservation", upstream
    if upstream.startswith("/notifications"):
        return "notification", upstream
    if upstream.startswith("/assistant"):
        return "ai", upstream
    return None


def is_protected(path: str) -> bool:
    if path.startswith("/api/admin"):
        return True
    return any(path == prefix or path.startswith(prefix + "/") for prefix in PROTECTED_PREFIXES)


def timeout_for(upstream: str, method: str) -> float:
    if upstream.startswith("/assistant"):
        return AI_TIMEOUT
    if method == "POST" and upstream.endswith("/confirm"):
        return CONFIRM_TIMEOUT
    return GATEWAY_TIMEOUT


def forward_headers(request: Request) -> dict:
    headers = {}
    for key in ("authorization", "accept", "accept-language", "content-type", "user-agent"):
        value = request.headers.get(key)
        if value:
            headers[key] = value
    headers["x-request-id"] = request.headers.get("x-request-id") or str(uuid.uuid4())
    headers["x-forwarded-host"] = request.headers.get("host", "")
    headers["x-forwarded-for"] = client_ip(request)
    return headers


def clean_response_headers(upstream: httpx.Response) -> dict:
    headers = {
        key: value
        for key, value in upstream.headers.items()
        if key.lower() in PASS_RESPONSE_HEADERS and key.lower() not in HOP_BY_HOP
    }
    # Allow cross-origin image loading for canvas textures (posters on the shelf).
    headers["Access-Control-Allow-Origin"] = "*"
    headers["Access-Control-Allow-Headers"] = "Range"
    headers["Access-Control-Expose-Headers"] = "Content-Length, Content-Range"
    return headers


def service_url(service: str) -> str:
    return {
        "user": USER_SERVICE_URL,
        "movie": MOVIE_SERVICE_URL,
        "reservation": RESERVATION_SERVICE_URL,
        "notification": NOTIFICATION_SERVICE_URL,
        "ai": AI_SERVICE_URL,
    }[service]


async def call_upstream(
    service: str,
    method: str,
    upstream_path: str,
    query: str,
    headers: dict,
    body: bytes,
    timeout: float,
) -> httpx.Response:
    params = httpx.QueryParams(query) if query else None
    limits = httpx.Limits(max_connections=100, max_keepalive_connections=30)
    timeout_config = httpx.Timeout(timeout, connect=CONNECT_TIMEOUT)

    if service != "reservation":
        async with httpx.AsyncClient(timeout=timeout_config, limits=limits) as client:
            return await client.request(
                method,
                service_url(service) + upstream_path,
                params=params,
                headers=headers,
                content=body or None,
            )

    targets = reservation_balancer.targets()
    start = reservation_balancer.next()
    if start in targets:
        targets.remove(start)
        targets.insert(0, start)
    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=timeout_config, limits=limits) as client:
        for target in targets:
            try:
                return await client.request(
                    method,
                    target + upstream_path,
                    params=params,
                    headers=headers,
                    content=body or None,
                )
            except (httpx.ConnectError, httpx.ConnectTimeout, ConnectionRefusedError) as exc:
                last_error = exc
                logger.warning("reservation target %s unavailable: %s", target, exc)
                continue
        if last_error:
            raise last_error
        raise httpx.ConnectError("No reservation replica available")


async def proxy_request(request: Request, service: str, upstream_path: str) -> Response:
    started = time.perf_counter()
    timeout = timeout_for(upstream_path, request.method)
    try:
        body = await request.body()
        upstream = await call_upstream(
            service,
            request.method,
            upstream_path,
            request.url.query,
            forward_headers(request),
            body,
            timeout,
        )
    except (httpx.ConnectError, httpx.ConnectTimeout, OSError, socket.gaierror) as exc:
        logger.warning("%s unavailable: %s", service, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"The {service} service is temporarily unavailable. Please try again shortly.",
        )
    except httpx.TimeoutException as exc:
        logger.warning("%s timed out: %s", service, exc)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The request took too long. Please try again.",
        )
    except httpx.HTTPError as exc:
        logger.warning("%s request failed: %s", service, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Upstream service error.")
    duration = round((time.perf_counter() - started) * 1000, 2)
    logger.info(
        "proxied",
        extra={
            "event": "gateway.proxy",
            "method": request.method,
            "path": upstream_path,
            "status_code": upstream.status_code,
            "duration_ms": duration,
        },
    )
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=clean_response_headers(upstream),
        media_type=upstream.headers.get("content-type"),
        background=None,
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("starting", extra={"event": "service.start"})
    yield
    logger.info("stopped", extra={"event": "service.stop"})


app = FastAPI(title="Nocturne API Gateway", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
    ).split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
    max_age=600,
)
app.add_middleware(RequestLogMiddleware, service=SERVICE, logger=logger)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": SERVICE,
        "timestamp": time.time(),
        "reservation_replicas": len(reservation_balancer.targets()),
    }


@app.get("/api/health")
def api_health():
    return health()


@app.get("/api/health/upstreams")
async def health_upstreams():
    services = {
        "user": USER_SERVICE_URL,
        "movie": MOVIE_SERVICE_URL,
        "reservation": RESERVATION_SERVICE_URL,
        "notification": NOTIFICATION_SERVICE_URL,
        "ai": AI_SERVICE_URL,
    }

    async def check(name: str, base: str):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(2.5, connect=1.5)) as client:
                response = await client.get(base + "/health")
            return name, response.status_code < 500, response.status_code
        except Exception as exc:
            return name, False, str(exc)

    results = await asyncio.gather(*(check(name, base) for name, base in services.items()))
    return {
        "items": [{"service": name, "up": up, "detail": detail} for name, up, detail in results],
        "timestamp": time.time(),
    }


@app.api_route("/media/{path:path}", methods=["GET", "HEAD"])
async def media(path: str, request: Request):
    return await proxy_request(request, "movie", "/media/" + path)


@app.api_route(
    "/api/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def gateway(path: str, request: Request):
    full_path = request.url.path
    if full_path.startswith("/api/auth/") and not auth_limiter.allow(client_ip(request)):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Please wait a minute and try again.",
        )
    user = require_user(request)
    if is_protected(full_path):
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sign in to continue.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if full_path.startswith("/api/admin") and user.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrator access required.",
            )
    route = route_backend(full_path, request.method)
    if not route:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    service, upstream_path = route
    return await proxy_request(request, service, upstream_path)
