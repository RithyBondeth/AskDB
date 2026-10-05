"""Read-only database access.

The SQL validator is the first safety layer; this module is the second. Every
connection is opened read-only and with a statement timeout, so even a statement
that slips past the parser cannot modify data or run forever:

- SQLite: ``mode=ro`` URI, timeout via the progress handler
- PostgreSQL: ``default_transaction_read_only`` and ``statement_timeout``
- MySQL / MariaDB: ``SET SESSION TRANSACTION READ ONLY`` and
  ``max_execution_time`` (MySQL) or ``max_statement_time`` (MariaDB)

Other databases are refused rather than run with weaker guarantees.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url

# How long to wait for a network database to accept a connection.
CONNECT_TIMEOUT_S = 10


class QueryError(Exception):
    """The database rejected or failed to run a query."""


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[list[Any]]
    truncated: bool


def make_engine(database_url: str, timeout_s: float) -> Engine:
    url = make_url(database_url)
    backend = url.get_backend_name()

    if backend == "sqlite":
        path = url.database
        if not path or path == ":memory:":
            raise ValueError("AskDB needs a file-backed SQLite database")

        def connect() -> sqlite3.Connection:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
            # Don't let functions or virtual tables named in the schema run on our behalf;
            # matters for databases people upload (SQLite's guidance for untrusted files).
            conn.execute("PRAGMA trusted_schema = OFF")
            _install_sqlite_timeout(conn, timeout_s)
            return conn

        return create_engine("sqlite://", creator=connect)

    ms = int(timeout_s * 1000)
    if backend in ("postgresql", "postgres"):  # "postgres://" is common in hosted URLs
        return create_engine(
            url.set(drivername="postgresql+psycopg"),
            pool_pre_ping=True,
            connect_args={
                "connect_timeout": CONNECT_TIMEOUT_S,
                "options": f"-c default_transaction_read_only=on -c statement_timeout={ms}",
            },
        )

    if backend in ("mysql", "mariadb"):
        engine = create_engine(
            url.set(drivername=f"{backend}+pymysql"),
            pool_pre_ping=True,
            connect_args={"connect_timeout": CONNECT_TIMEOUT_S},
        )

        @event.listens_for(engine, "connect")
        def _session(dbapi_conn, _record):
            with dbapi_conn.cursor() as cur:
                cur.execute("SET SESSION TRANSACTION READ ONLY")
                cur.execute("SELECT VERSION()")
                if "mariadb" in str(cur.fetchone()[0]).lower():
                    # MariaDB has no max_execution_time; its limit is in seconds.
                    cur.execute(f"SET SESSION max_statement_time = {timeout_s:g}")
                else:
                    cur.execute(f"SET SESSION max_execution_time = {ms}")

        return engine

    # Anything else would get neither a guaranteed read-only session nor a timeout.
    raise ValueError(
        f"AskDB supports SQLite, PostgreSQL and MySQL/MariaDB databases, not {backend!r}."
    )


def _install_sqlite_timeout(conn: sqlite3.Connection, timeout_s: float) -> None:
    """SQLite has no statement timeout, so abort long queries via the progress handler."""
    state = {"deadline": 0.0}

    def reset(*_: Any) -> None:
        state["deadline"] = time.monotonic() + timeout_s

    def check() -> int:
        return 1 if state["deadline"] and time.monotonic() > state["deadline"] else 0

    conn.set_progress_handler(check, 10_000)
    conn.set_trace_callback(reset)  # called at the start of every statement


def run_query(engine: Engine, sql: str, row_limit: int, offset: int = 0) -> QueryResult:
    """Run a query and return up to `row_limit` rows, after skipping `offset` rows.
    Rows are skipped client-side so the SQL itself is never rewritten."""
    try:
        with engine.connect() as conn:
            result = conn.exec_driver_sql(sql)
            columns = list(result.keys())
            skipped = 0
            while skipped < offset:
                chunk = result.fetchmany(min(1000, offset - skipped))
                if not chunk:
                    break
                skipped += len(chunk)
            fetched = result.fetchmany(row_limit + 1)
    except Exception as e:  # driver errors vary by backend
        raise QueryError(_clean_error(e)) from e
    rows = [list(r) for r in fetched[:row_limit]]
    return QueryResult(columns=columns, rows=rows, truncated=len(fetched) > row_limit)


def iter_query(engine: Engine, sql: str, max_rows: int) -> tuple[list[str], Iterator[list[Any]]]:
    """Columns, then rows streamed one at a time (at most `max_rows`), for exports
    too big to hold in memory. Errors before the first row raise QueryError."""
    conn = engine.connect()
    try:
        result = conn.execution_options(stream_results=True).exec_driver_sql(sql)
        columns = list(result.keys())
    except Exception as e:
        conn.close()
        raise QueryError(_clean_error(e)) from e

    def rows() -> Iterator[list[Any]]:
        try:
            sent = 0
            while sent < max_rows:
                chunk = result.fetchmany(min(1000, max_rows - sent))
                if not chunk:
                    return
                sent += len(chunk)
                yield from (list(r) for r in chunk)
        finally:
            conn.close()

    return columns, rows()


# How each database reports a cancelled statement: SQLite (progress handler),
# PostgreSQL (statement_timeout), MySQL and MariaDB.
_TIMEOUT_SIGNS = (
    "interrupted",
    "statement timeout",
    "max_statement_time",
    "execution time exceeded",
)


def _clean_error(e: Exception) -> str:
    orig = getattr(e, "orig", None)
    msg = str(orig or e)
    if any(sign in msg.lower() for sign in _TIMEOUT_SIGNS):
        return "Query timed out and was cancelled."
    return msg.split("\n[SQL:")[0].strip()
