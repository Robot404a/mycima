import os
import pathlib
import time

TEST_URL = os.getenv("TEST_DATABASE_URL", "postgresql://reservation:reservation_dev@localhost:5433/reservation_test")
os.environ["DATABASE_URL"] = TEST_URL
os.environ["JWT_SECRET"] = "test-secret-which-is-long-enough-32b"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["MOVIE_LOOKUP"] = "stub"
os.environ["CLEANUP_INTERVAL_SECONDS"] = "3600"

import jwt
import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _prepare_database():
    """Creates a SEPARATE test database (never touches your dev data) and applies db/schema.sql."""
    dbname = conninfo_to_dict(TEST_URL)["dbname"]
    with psycopg.connect(make_conninfo(TEST_URL, dbname="postgres"), autocommit=True) as admin:
        exists = admin.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,)).fetchone()
        if not exists:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
    with psycopg.connect(TEST_URL, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        conn.execute((ROOT / "db" / "schema.sql").read_text())


@pytest.fixture(scope="session")
def client():
    _prepare_database()
    import main
    with TestClient(main.app) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_tables(client):
    with psycopg.connect(TEST_URL, autocommit=True) as conn:
        conn.execute("TRUNCATE seat_claims, bookings, holds RESTART IDENTITY CASCADE")


@pytest.fixture
def db_exec():
    def run(query, params=None):
        with psycopg.connect(TEST_URL, autocommit=True) as conn:
            conn.execute(query, params)
    return run


def auth(user_id: int, role: str = "user") -> dict:
    token = jwt.encode(
        {"sub": str(user_id), "role": role, "exp": int(time.time()) + 3600}, "test-secret-which-is-long-enough-32b", algorithm="HS256"
    )
    return {"Authorization": f"Bearer {token}"}
