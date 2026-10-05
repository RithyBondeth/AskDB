"""The Postgres connection stays read-only and time-limited on every query.

Needs a real server: set ASKDB_TEST_POSTGRES_URL to a role that may create a table,
e.g. postgresql://postgres@localhost/postgres (CI runs one). Skipped otherwise.
"""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from askdb.db import QueryError, make_engine, run_query

URL = os.environ.get("ASKDB_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not URL, reason="ASKDB_TEST_POSTGRES_URL not set")


@pytest.fixture
def engine():
    admin = create_engine(make_url(URL).set(drivername="postgresql+psycopg"))
    with admin.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS askdb_test_t")
        conn.exec_driver_sql("CREATE TABLE askdb_test_t (id INT)")
        conn.exec_driver_sql("INSERT INTO askdb_test_t VALUES (1)")
    # One pooled connection, so every query below reuses the same session.
    eng = make_engine(URL, timeout_s=1)
    eng.pool._pool.maxsize = 1  # QueuePool: keep one connection
    yield eng
    eng.dispose()
    with admin.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS askdb_test_t")
    admin.dispose()


def test_reads_work(engine):
    assert run_query(engine, "SELECT id FROM askdb_test_t", 10).rows == [[1]]


def test_writes_are_rejected(engine):
    with pytest.raises(QueryError, match="read-only"):
        run_query(engine, "INSERT INTO askdb_test_t VALUES (2)", 10)


def test_session_settings_changed_by_a_query_dont_carry_over(engine):
    # A query that turns off the session defaults (the validator blocks set_config,
    # but this is the second layer) only changes its own transaction: run_query never
    # commits, so the rollback undoes it and the next query on the same pooled
    # connection is still read-only and timed. Committing in run_query would break this.
    run_query(
        engine,
        "SELECT set_config('default_transaction_read_only', 'off', false),"
        " set_config('statement_timeout', '0', false)",
        10,
    )
    with pytest.raises(QueryError, match="read-only"):
        run_query(engine, "INSERT INTO askdb_test_t VALUES (2)", 10)
    with pytest.raises(QueryError, match="timed out"):
        run_query(engine, "SELECT pg_sleep(5)", 10)
