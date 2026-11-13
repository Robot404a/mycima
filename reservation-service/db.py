"""PostgreSQL connection pool (psycopg 3). Rows come back as dicts."""
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

import config

pool: ConnectionPool | None = None
schema_ready = False
SCHEMA_FILE = Path(__file__).resolve().parent / "db" / "schema.sql"
_SCHEMA_LOCK_ID = 727_001


def init_pool() -> None:
    global pool, schema_ready
    schema_ready = False
    if pool is None:
        pool = ConnectionPool(
            config.DATABASE_URL,
            min_size=config.DB_POOL_MIN,
            max_size=config.DB_POOL_MAX,
            kwargs={"row_factory": dict_row},
            open=False,
        )
        # wait=False: the service still starts if Postgres is late; /health reports it.
        pool.open(wait=False)


def close_pool() -> None:
    global pool
    if pool is not None:
        pool.close()
        pool = None


def get_conn():
    """Use as `with get_conn() as conn:` -> commits on success, rolls back on error."""
    assert pool is not None, "database pool is not initialised"
    return pool.connection(timeout=5)


def ping() -> bool:
    try:
        with get_conn() as conn:
            conn.execute("SELECT 1")
        return True
    except (psycopg.Error, Exception):
        return False


def apply_schema() -> None:
    """Create the tables if they do not exist yet. Safe to run repeatedly and from several replicas."""
    global schema_ready
    script = SCHEMA_FILE.read_text(encoding="utf-8")
    with get_conn() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (_SCHEMA_LOCK_ID,))
        conn.execute(script)
    schema_ready = True
