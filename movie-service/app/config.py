"""Environment-driven configuration for the Movie Service."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


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


@dataclass(frozen=True)
class Settings:
    service_name: str = "movie-service"
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'movie_service.db').as_posix()}")
    )
    jwt_secret: str = field(default_factory=lambda: os.getenv("JWT_SECRET", "dev-secret-change-me"))
    jwt_algorithm: str = field(default_factory=lambda: os.getenv("JWT_ALGORITHM", "HS256"))
    seed_on_startup: bool = field(default_factory=lambda: _env_bool("SEED_ON_STARTUP", True))
    seed_days: int = field(default_factory=lambda: _env_int("SEED_DAYS", 7))
    cinema_timezone: str = field(default_factory=lambda: os.getenv("CINEMA_TIMEZONE", "Africa/Casablanca"))
    media_cache_dir: Path = field(
        default_factory=lambda: Path(os.getenv("POSTER_CACHE_DIR", str(BASE_DIR / "media_cache")))
    )
    poster_base_url: str = field(
        default_factory=lambda: os.getenv("POSTER_BASE_URL", "https://image.tmdb.org/t/p/w500").rstrip("/")
    )
    poster_timeout_seconds: float = field(default_factory=lambda: _env_float("POSTER_TIMEOUT_SECONDS", 8.0))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))


settings = Settings()
