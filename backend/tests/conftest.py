import sqlite3
from pathlib import Path

import pytest

from askdb.db import make_engine
from askdb.generate import Generation, Repair


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "shop.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE customer (id INTEGER PRIMARY KEY, name TEXT, country TEXT);
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER REFERENCES customer(id),
            total REAL,
            ordered_at TEXT
        );
        INSERT INTO customer VALUES (1, 'Ada', 'UK'), (2, 'Linus', 'FI'), (3, 'Grace', 'US');
        INSERT INTO orders VALUES
            (1, 1, 10.0, '2024-01-05'), (2, 1, 15.5, '2024-02-10'),
            (3, 2, 7.25, '2024-02-11'), (4, 3, 30.0, '2024-03-01');
        """
    )
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def engine(db_path: Path):
    return make_engine(f"sqlite:///{db_path}", timeout_s=5)


class ScriptedGenerator:
    """A fake LLM that returns a fixed sequence of queries and records repairs."""

    def __init__(self, *sqls: str):
        self.sqls = list(sqls)
        self.calls: list[list[Repair] | None] = []

    def generate(self, question: str, repairs: list[Repair] | None = None) -> Generation:
        self.calls.append(list(repairs) if repairs else None)
        return Generation(sql=self.sqls[len(self.calls) - 1], explanation="scripted")


@pytest.fixture
def scripted():
    return ScriptedGenerator
