"""PostgreSQL connection pool (psycopg 3). Rows come back as dicts."""
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

import config

pool: ConnectionPool | None = None


def init_pool() -> None:
    global pool
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
