"""Pytest bootstrap: the assistant runs on a throwaway SQLite database."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

SERVICE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVICE_DIR))

TEST_DB = SERVICE_DIR / "test_assistant.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["JWT_SECRET"] = "test-secret-please-change-it"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["LLM_API_KEY"] = "test-key"
os.environ["LLM_BASE_URL"] = "https://llm.invalid/v1"
os.environ["LLM_MODEL"] = "test-model"
os.environ["LLM_MODEL_FALLBACKS"] = ""
os.environ["GATEWAY_INTERNAL_URL"] = "http://gateway.invalid/api"

import jwt  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import guard  # noqa: E402
from main import app  # noqa: E402

JWT_SECRET = os.environ["JWT_SECRET"]


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def allow_topic_guard(monkeypatch):
    """By default the classifier allows every message; guard tests override this."""

    async def allow(messages, tools=None, temperature=None, max_tokens=None):
        return {"role": "assistant", "content": "ALLOW"}

    monkeypatch.setattr(guard, "complete", allow)
    return allow


def make_token(user_id: str, role: str = "user") -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "email": f"user{user_id}@mycima.test",
        "role": role,
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


@pytest.fixture
def auth():
    def _auth(user_id: str = "1", role: str = "user") -> dict[str, str]:
        return {"Authorization": f"Bearer {make_token(user_id, role)}"}

    return _auth
