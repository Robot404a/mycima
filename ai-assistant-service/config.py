"""Configuration of the AI assistant service (environment driven)."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Local runs: make the repository's shared/ folder importable (in Docker, PYTHONPATH=/app does it).
_REPO_ROOT = BASE_DIR.parent
if (_REPO_ROOT / "shared").is_dir() and str(_REPO_ROOT) not in sys.path:
    sys.path.append(str(_REPO_ROOT))


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    service_name: str = "ai-assistant-service"

    # Assistant conversations live in their own database (ai_assistant_db).
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", f"sqlite:///{(BASE_DIR / 'assistant.db').as_posix()}"
        )
    )

    # Authentication: the gateway validates the token, we decode it again to learn who asks.
    jwt_secret: str = field(
        default_factory=lambda: os.getenv("JWT_SECRET", "mycima-dev-secret-change-me-in-production")
    )
    jwt_algorithm: str = field(default_factory=lambda: os.getenv("JWT_ALGORITHM", "HS256"))

    # Tools call the platform through the gateway, with the guest's own token.
    gateway_url: str = field(
        default_factory=lambda: os.getenv("GATEWAY_INTERNAL_URL", "http://gateway:8000/api").rstrip("/")
    )
    gateway_timeout_seconds: float = field(
        default_factory=lambda: _float("GATEWAY_TIMEOUT_SECONDS", 20.0)
    )

    # LLM provider: any OpenAI-compatible endpoint. Defaults to Gemini's compatible API.
    llm_base_url: str = field(
        default_factory=lambda: os.getenv(
            "LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai"
        ).rstrip("/")
    )
    llm_api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", "").strip())
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gemini-flash-lite-latest"))
    llm_model_fallbacks: str = field(
        default_factory=lambda: os.getenv(
            "LLM_MODEL_FALLBACKS", "gemini-2.5-flash,gemini-2.5-flash-lite"
        )
    )
    llm_timeout_seconds: float = field(
        default_factory=lambda: _float("LLM_TIMEOUT_SECONDS", 45.0)
    )
    llm_max_iterations: int = field(default_factory=lambda: _int("LLM_MAX_ITERATIONS", 5))
    llm_temperature: float = field(default_factory=lambda: _float("LLM_TEMPERATURE", 0.35))
    llm_max_tokens: int = field(default_factory=lambda: _int("LLM_MAX_TOKENS", 1400))

    # Cinema domain
    cinema_timezone: str = field(
        default_factory=lambda: os.getenv("CINEMA_TIMEZONE", "Africa/Casablanca")
    )
    max_seats_per_hold: int = field(default_factory=lambda: _int("MAX_SEATS_PER_HOLD", 8))
    proposal_ttl_minutes: int = field(default_factory=lambda: _int("PROPOSAL_TTL_MINUTES", 15))
    history_limit: int = field(default_factory=lambda: _int("HISTORY_LIMIT", 40))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    @property
    def models(self) -> list[str]:
        chain = [self.llm_model]
        chain += [item.strip() for item in self.llm_model_fallbacks.split(",") if item.strip()]
        return list(dict.fromkeys(chain))


settings = Settings()
