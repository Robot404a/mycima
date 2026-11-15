"""All settings come from environment variables, with local-dev defaults."""
import os
import sys
from pathlib import Path

# Local runs: make the repo's shared/ folder importable (in Docker, PYTHONPATH=/app does this).
_REPO_ROOT = Path(__file__).resolve().parent.parent
if (_REPO_ROOT / "shared").is_dir() and str(_REPO_ROOT) not in sys.path:
    sys.path.append(str(_REPO_ROOT))


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


# Database (local dev: its own Postgres from docker-compose.yml, on port 5434)
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://notification:notification_dev@localhost:5434/notification"
)
DB_POOL_MIN = _int("DB_POOL_MIN", 2)
DB_POOL_MAX = _int("DB_POOL_MAX", 10)

# Email (local dev: Mailpit catches everything, web UI on http://localhost:8025)
SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = _int("SMTP_PORT", 1025)
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "false").lower() == "true"
EMAIL_FROM = os.getenv("EMAIL_FROM", "no-reply@mycima.local")

# Delivery behaviour
MAX_SEND_ATTEMPTS = _int("MAX_SEND_ATTEMPTS", 3)

# Only used by the local fallback in auth.py. Must match the User service secret.
JWT_SECRET = os.getenv("JWT_SECRET", "mycima-dev-secret-change-me-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# Retrying failed emails
RETRY_INTERVAL_SECONDS = _int("RETRY_INTERVAL_SECONDS", 30)   # how often the loop runs
RETRY_DELAY_SECONDS = _int("RETRY_DELAY_SECONDS", 60)         # min wait between attempts

# Shared secret for service-to-service calls (reservation-service -> us). Never exposed via the gateway.
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "dev-internal-key-change-me")