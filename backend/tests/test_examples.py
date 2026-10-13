"""Few-shot examples generated from an upload's own schema."""

import sqlite3

from askdb.db import make_engine, run_query
from askdb.examples import schema_examples, suggest_questions
from askdb.schema import introspect
from askdb.validate import validate_sql


def _examples(engine):
    return schema_examples(introspect(engine), engine)


def test_one_of_each_kind_and_every_query_runs(engine):
    examples = _examples(engine)
    questions = [q for q, _ in examples]
    # No group-by: the only numeric non-key column (orders.total) has no label beside it.
    assert questions == [
        "Which customer name has the most orders rows?",
        "Total per month in orders",
    ]
    joined = examples[0][1]
    assert "JOIN customer p ON p.id = c.customer_id" in joined
    for _, sql in examples:
        validate_sql(sql, "sqlite")
        assert run_query(engine, sql, 5).rows


def test_monthly_example_uses_sqlite_dates(engine):
    sql = dict(_examples(engine))["Total per month in orders"]
    assert "strftime('%Y-%m', ordered_at)" in sql
    assert run_query(engine, sql, 5).rows[0] == ["2024-01", 10.0]


def test_awkward_identifiers_are_quoted_only_when_needed(tmp_path):
    path = tmp_path / "odd.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE "order" ("Product Name" TEXT, Revenue REAL);
        INSERT INTO "order" VALUES ('Dock', 220), ('Laptop', 2400);
        """
    )
    conn.commit()
    conn.close()
    engine = make_engine(f"sqlite:///{path}", 5)
    (question, sql), *_ = _examples(engine)
    assert question == "Top 10 Product Name by total Revenue in order"
    assert 'FROM "order"' in sql and "SUM(Revenue)" in sql and '"Product Name"' in sql
    assert run_query(engine, sql, 5).rows[0] == ["Laptop", 2400.0]


def test_queries_that_return_nothing_are_not_examples(tmp_path):
    path = tmp_path / "empty.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE sales (region TEXT, amount REAL, sold_on TEXT)")
    conn.commit()
    conn.close()
    engine = make_engine(f"sqlite:///{path}", 5)
    assert _examples(engine) == []
    assert suggest_questions(introspect(engine))  # suggestions don't need data


def test_foreign_keys_are_not_measures(engine):
    # orders.customer_id is a key: summing it would be a nonsense example.
    assert all("customer_id)" not in sql for _, sql in _examples(engine))
