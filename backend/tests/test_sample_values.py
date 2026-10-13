"""Sample values in the prompt's schema."""

import sqlite3

import pytest

from askdb.config import Settings
from askdb.db import make_engine
from askdb.pipeline import AskDB
from askdb.schema import Column, Table, introspect, sample_values


def _table(engine, name):
    return next(t for t in introspect(engine).tables if t.name == name)


@pytest.fixture
def shop(tmp_path):
    path = tmp_path / "shop.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            status TEXT,
            customer_name TEXT,
            customer_email TEXT,
            api_key TEXT,
            note TEXT,
            placed_at DATETIME,
            amount REAL
        );
        """
    )
    rows = []
    for i in range(60):
        status = ["shipped", "shipped", "shipped", "pending", "cancelled"][i % 5]
        note = "line one\nline two" if i == 0 else ("x" * 50 if i == 1 else "ok")
        rows.append(
            (status, f"Customer {i}", f"c{i}@example.com", f"k{i}", note,
             f"2024-01-{i % 28 + 1:02d} 10:00:00", i * 1.5)
        )  # fmt: skip
    conn.executemany(
        "INSERT INTO orders (status, customer_name, customer_email, api_key, note, placed_at, "
        "amount) VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()
    return make_engine(f"sqlite:///{path}", 5)


def test_categorical_columns_show_their_most_common_values(shop):
    t = _table(shop, "orders")
    sample_values(shop, t, 3)
    s = {c.name: c.samples for c in t.columns}
    assert s["status"] == ["shipped", "cancelled", "pending"]  # most common first
    assert s["note"] == ["ok"]  # multi-line and over-long values are left out


def test_what_never_gets_samples(shop):
    t = _table(shop, "orders")
    sample_values(shop, t, 3)
    s = {c.name: c.samples for c in t.columns}
    assert s["customer_name"] == []  # 60 distinct names: not categorical
    assert s["customer_email"] == []  # personal contact details
    assert s["api_key"] == []  # secrets
    assert s["id"] == [] and s["amount"] == []  # keys and numbers


def test_dates_show_one_value_for_the_format(shop):
    t = _table(shop, "orders")
    sample_values(shop, t, 3)
    assert next(c for c in t.columns if c.name == "placed_at").samples == ["2024-01-01 10:00:00"]


def test_foreign_keys_get_no_samples(engine):
    t = _table(engine, "orders")
    sample_values(engine, t, 3)
    assert next(c for c in t.columns if c.name == "customer_id").samples == []
    customer = _table(engine, "customer")
    sample_values(engine, customer, 3)
    # Ties are alphabetical, so the prompt is identical between questions.
    assert next(c for c in customer.columns if c.name == "country").samples == ["FI", "UK", "US"]


def test_ddl_shows_samples_after_comments_and_stays_valid_sql():
    t = Table(
        "shop",
        [
            Column("id", "INTEGER", primary_key=True),
            Column("region", "TEXT", comment="Sales region", samples=["North", "O'Hare"]),
            Column("status", "TEXT", samples=["open"]),
        ],
    )
    ddl = t.ddl()
    assert "  region TEXT, -- Sales region; e.g. 'North', 'O''Hare'" in ddl
    assert "  status TEXT -- e.g. 'open'\n);" in ddl
    conn = sqlite3.connect(":memory:")
    conn.execute(ddl)  # the comments don't break the statement


def test_prompt_includes_samples_for_linked_tables_only_once(db_path, monkeypatch):
    import askdb.pipeline as pipeline

    calls = []
    real = pipeline.sample_values
    monkeypatch.setattr(
        pipeline, "sample_values", lambda e, t, n: calls.append(t.name) or real(e, t, n)
    )
    db = AskDB.for_database(f"sqlite:///{db_path}", Settings(database_url=f"sqlite:///{db_path}"))
    gen = db.generator_for("revenue by country", provider="claude", api_key="k")
    assert "country TEXT -- e.g. 'FI', 'UK', 'US'" in gen.system_prompt
    db.generator_for("orders per customer", provider="claude", api_key="k")
    assert sorted(calls) == ["customer", "orders"]  # each table read once


def test_sample_values_can_be_turned_off(db_path):
    s = Settings(database_url=f"sqlite:///{db_path}", sample_values=0)
    db = AskDB.for_database(f"sqlite:///{db_path}", s)
    gen = db.generator_for("revenue by country", provider="claude", api_key="k")
    assert "e.g." not in gen.system_prompt
