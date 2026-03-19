import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from flask import current_app
import os

_pool: ThreadedConnectionPool = None


def init_db():
    global _pool
    if not _pool:
        url = os.getenv("DATABASE_URL")
        db_host = os.getenv("DB_HOST")
        if db_host:
            _pool = ThreadedConnectionPool(
                minconn=2, maxconn=10,
                host=db_host,
                port=os.getenv("DB_PORT", 5432),
                dbname=os.getenv("DB_NAME", "postgres"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD")
            )
        else:
            _pool = ThreadedConnectionPool(minconn=2, maxconn=10, dsn=url)


@contextmanager
def get_db():
    """Yields a psycopg2 connection; auto-commits or rolls back."""
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


@contextmanager
def get_cursor():
    """Yields a RealDictCursor (rows as dicts)."""
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
