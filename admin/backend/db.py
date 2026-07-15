import os
import logging
from contextlib import contextmanager

import psycopg2
import psycopg2.pool
import psycopg2.extras
import psycopg2.errors

logger = logging.getLogger(__name__)

_pool = None


def init_pool():
    global _pool
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL non impostata. "
            "Impostare DATABASE_URL=postgresql://user:pass@host:5432/dbname"
        )
    _pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=2,
        maxconn=10,
        dsn=database_url,
        cursor_factory=psycopg2.extras.RealDictCursor,
        connect_timeout=10,
        options="-c statement_timeout=30000",
    )
    logger.info("PostgreSQL connection pool inizializzato")


def close_pool():
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None
        logger.info("PostgreSQL connection pool chiuso")


def get_conn():
    if _pool is None:
        init_pool()
    return _pool.getconn()


def put_conn(conn):
    if _pool and conn:
        try:
            if conn.status != psycopg2.extensions.STATUS_READY:
                conn.rollback()
        except Exception:
            pass
        _pool.putconn(conn)


@contextmanager
def db_connection():
    conn = get_conn()
    try:
        yield conn
    finally:
        put_conn(conn)


def execute(query, params=None):
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            try:
                return cur.fetchall()
            except psycopg2.errors.ProgrammingError:
                return []


def execute_one(query, params=None):
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            try:
                return cur.fetchone()
            except psycopg2.errors.ProgrammingError:
                return None


def execute_write(query, params=None):
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            conn.commit()
            return cur.rowcount


def execute_many(query, params_list):
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(query, params_list)
            conn.commit()
