"""All settings come from environment variables, with local-dev defaults."""
import os
import sys
from decimal import Decimal
from pathlib import Path

# Local runs: make the repo's shared/ folder importable (in Docker, PYTHONPATH=/app does this).
_REPO_ROOT = Path(__file__).resolve().parent.parent
if (_REPO_ROOT / "shared").is_dir() and str(_REPO_ROOT) not in sys.path:
    sys.path.append(str(_REPO_ROOT))


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


# Database (local dev: the Postgres started by docker-compose.yml on port 5433)
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://reservation:reservation_dev@localhost:5433/reservation"
)
DB_POOL_MIN = _int("DB_POOL_MIN", 2)
DB_POOL_MAX = _int("DB_POOL_MAX", 10)

# Business rules
HOLD_TTL_SECONDS = _int("HOLD_TTL_SECONDS", 600)          # how long seats stay locked
MAX_SEATS_PER_HOLD = _int("MAX_SEATS_PER_HOLD", 8)
CLEANUP_INTERVAL_SECONDS = _int("CLEANUP_INTERVAL_SECONDS", 30)

# Where showtime / hall information comes from.
#   stub -> built-in hall (rows A-H, 12 seats each); lets you work before the Movie service is ready
#   http -> ask the Movie service (see movie_client.py for the expected response shape)
MOVIE_LOOKUP = os.getenv("MOVIE_LOOKUP", "stub").lower()
MOVIE_SERVICE_URL = os.getenv("MOVIE_SERVICE_URL", "http://movie-service:8000").rstrip("/")
MOVIE_TIMEOUT_SECONDS = float(os.getenv("MOVIE_TIMEOUT_SECONDS", "5"))
STUB_ROWS = _int("STUB_ROWS", 8)
STUB_SEATS_PER_ROW = _int("STUB_SEATS_PER_ROW", 12)
STUB_PRICE = Decimal(os.getenv("STUB_PRICE", "8.00"))

# Only used by the local fallback in auth.py (when shared/ is not available yet).
# Must match the secret used by the User service.
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
