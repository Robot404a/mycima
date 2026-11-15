"""Environment-driven configuration for the MyCima payment service.

All configuration comes from environment variables. The defaults target the
standalone development setup described in ``README.md``; production and the
root Docker Compose deployment must set the values explicitly.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # payment-service/
REPO_ROOT = BASE_DIR.parent  # repository root (contains shared/)

# Make the project importable in every execution mode:
#   * BASE_DIR/generated -> top-level imports inside the generated protobuf files
#   * BASE_DIR           -> the ``app`` package when running from elsewhere
#   * REPO_ROOT          -> ``shared.auth`` / ``shared.logging_config``
# In Docker WORKDIR=/app and shared/ is copied to /app/shared, so BASE_DIR is
# enough there; locally shared/ lives next to payment-service/.
for _path in (BASE_DIR / "generated", BASE_DIR, REPO_ROOT):
    _text = str(_path)
    if _path.is_dir() and _text not in sys.path:
        sys.path.insert(0, _text)


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return default if value is None else value


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_csv_set(name: str, default: str) -> frozenset[str]:
    raw = os.getenv(name, default)
    values = {item.strip().upper() for item in raw.split(",") if item.strip()}
    return frozenset(values)


@dataclass(frozen=True)
class Settings:
    """Immutable runtime configuration."""

    service_name: str = "payment-service"

    # PostgreSQL owned exclusively by this service. The root Compose file must
    # provide a dedicated database and role (see README).
    database_url: str = field(
        default_factory=lambda: _env_str(
            "DATABASE_URL",
            "postgresql+psycopg://payment_svc:payment_svc_pass@localhost:5434/payment_db",
        )
    )
    database_connect_attempts: int = field(
        default_factory=lambda: _env_int("DATABASE_CONNECT_ATTEMPTS", 15)
    )
    database_connect_delay_seconds: float = field(
        default_factory=lambda: _env_float("DATABASE_CONNECT_DELAY_SECONDS", 2.0)
    )

    # JWT values are consumed by shared.auth at import time. They are repeated
    # here so health/diagnostics and documentation have one source of truth.
    jwt_secret: str = field(
        default_factory=lambda: _env_str(
            "JWT_SECRET", "mycima-dev-secret-change-me-in-production"
        )
    )
    jwt_algorithm: str = field(
        default_factory=lambda: _env_str("JWT_ALGORITHM", "HS256")
    )

    reservation_service_url: str = field(
        default_factory=lambda: _env_str(
            "RESERVATION_SERVICE_URL", "http://reservation-service:8000"
        ).rstrip("/")
    )
    reservation_timeout_seconds: float = field(
        default_factory=lambda: _env_float("RESERVATION_TIMEOUT_SECONDS", 5.0)
    )
    reservation_connect_timeout_seconds: float = field(
        default_factory=lambda: _env_float("RESERVATION_CONNECT_TIMEOUT_SECONDS", 2.0)
    )

    rest_port: int = field(default_factory=lambda: _env_int("REST_PORT", 8000))
    rest_host: str = field(default_factory=lambda: _env_str("REST_HOST", "0.0.0.0"))
    grpc_port: int = field(default_factory=lambda: _env_int("GRPC_PORT", 50051))
    grpc_host: str = field(default_factory=lambda: _env_str("GRPC_HOST", "0.0.0.0"))
    grpc_enabled: bool = field(default_factory=lambda: _env_bool("GRPC_ENABLED", True))

    # Simulated processor. Request-controlled outcomes (success/failure) are
    # accepted only when this flag is explicitly enabled for development tests.
    payment_simulation_enabled: bool = field(
        default_factory=lambda: _env_bool("PAYMENT_SIMULATION_ENABLED", False)
    )
    grpc_default_method: str = field(
        default_factory=lambda: _env_str("GRPC_DEFAULT_METHOD", "CARD").upper()
    )

    default_currency: str = field(
        default_factory=lambda: _env_str("DEFAULT_CURRENCY", "MAD").upper()
    )
    supported_currencies: frozenset[str] = field(
        default_factory=lambda: _env_csv_set("SUPPORTED_CURRENCIES", "MAD,USD,EUR")
    )

    # How long a duplicate idempotent request may wait for the first request to
    # finish before answering 409. Keeps concurrent retries useful without
    # holding a database transaction.
    idempotency_wait_seconds: float = field(
        default_factory=lambda: _env_float("IDEMPOTENCY_WAIT_SECONDS", 5.0)
    )
    idempotency_poll_seconds: float = field(
        default_factory=lambda: _env_float("IDEMPOTENCY_POLL_SECONDS", 0.05)
    )

    log_level: str = field(default_factory=lambda: _env_str("LOG_LEVEL", "INFO"))


settings = Settings()
