"""Read-only database access.

The SQL validator is the first safety layer; this module is the second. The
connection itself is opened read-only wherever the backend supports it, so even
a statement that slips past the parser cannot modify data.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url


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

    if backend == "postgresql":
        ms = int(timeout_s * 1000)
        return create_engine(
            url,
            connect_args={
                "options": f"-c default_transaction_read_only=on -c statement_timeout={ms}"
            },
        )

    engine = create_engine(url)

    @event.listens_for(engine, "begin")
    def _read_only(conn):  # pragma: no cover - backend specific
        conn.exec_driver_sql("SET TRANSACTION READ ONLY")

    return engine


def _install_sqlite_timeout(conn: sqlite3.Connection, timeout_s: float) -> None:
    """SQLite has no statement timeout, so abort long queries via the progress handler."""
    state = {"deadline": 0.0}

    def reset(*_: Any) -> None:
        state["deadline"] = time.monotonic() + timeout_s

    def check() -> int:
        return 1 if state["deadline"] and time.monotonic() > state["deadline"] else 0

    conn.set_progress_handler(check, 10_000)
    conn.set_trace_callback(reset)  # called at the start of every statement


def run_query(engine: Engine, sql: str, row_limit: int) -> QueryResult:
    try:
        with engine.connect() as conn:
            result = conn.exec_driver_sql(sql)
            columns = list(result.keys())
            fetched = result.fetchmany(row_limit + 1)
    except Exception as e:  # driver errors vary by backend
        raise QueryError(_clean_error(e)) from e
    rows = [list(r) for r in fetched[:row_limit]]
    return QueryResult(columns=columns, rows=rows, truncated=len(fetched) > row_limit)


def _clean_error(e: Exception) -> str:
    orig = getattr(e, "orig", None)
    msg = str(orig or e)
    if "interrupted" in msg.lower():
        return "Query timed out and was cancelled."
    return msg.split("\n[SQL:")[0].strip()
