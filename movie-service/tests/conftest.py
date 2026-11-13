"""Test configuration: the service runs on a throwaway SQLite database."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

SERVICE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVICE_DIR))

TEST_DB = SERVICE_DIR / "test_movie_service.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["POSTER_CACHE_DIR"] = str(SERVICE_DIR / "test_media_cache")
os.environ["SEED_ON_STARTUP"] = "true"
os.environ["SEED_DAYS"] = "3"
os.environ["JWT_SECRET"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402

from app.security import settings  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def admin_headers() -> dict[str, str]:
    import jwt

    token = jwt.encode({"sub": "1", "role": "admin"}, settings.jwt_secret, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}
