"""Pytest fixtures: a SQLite test database and a running app instance."""

from __future__ import annotations

import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

SERVICE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_DIR.parent
for path in (str(SERVICE_DIR), str(REPO_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

DATABASE_FILE = Path(tempfile.gettempdir()) / "mycima_users_test.db"
if DATABASE_FILE.exists():
    DATABASE_FILE.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DATABASE_FILE.as_posix()}"
os.environ["JWT_SECRET"] = "test-secret-0123456789abcdef0123456789"
os.environ["JWT_EXPIRE_MINUTES"] = "60"
os.environ["ADMIN_EMAIL"] = "admin@mycima.com"
os.environ["ADMIN_PASSWORD"] = "adminpass123"
os.environ["ADMIN_FULL_NAME"] = "Test Admin"

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"email": "admin@mycima.com", "password": "adminpass123"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def user(client: TestClient) -> dict:
    email = f"user-{uuid.uuid4().hex[:10]}@mycima.com"
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "secretpass1", "full_name": "Test User"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return {
        "id": body["user"]["id"],
        "email": email,
        "password": "secretpass1",
        "token": body["access_token"],
        "headers": {"Authorization": f"Bearer {body['access_token']}"},
    }
