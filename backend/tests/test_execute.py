import pytest

from askdb.db import QueryError, run_query
from askdb.execute import AnswerError, answer


def test_happy_path(engine, scripted):
    gen = scripted("SELECT name FROM customer ORDER BY id")
    ans = answer("names?", gen, engine, "sqlite")
    assert ans.result.columns == ["name"]
    assert ans.result.rows == [["Ada"], ["Linus"], ["Grace"]]
    assert len(ans.attempts) == 1


def test_self_corrects_after_db_error(engine, scripted):
    gen = scripted("SELECT nme FROM customer", "SELECT name FROM customer ORDER BY id LIMIT 1")
    ans = answer("first customer?", gen, engine, "sqlite")
    assert ans.result.rows == [["Ada"]]
    assert ans.attempts[0].stage == "execute"
    assert "nme" in ans.attempts[0].error
    # the failed SQL and its error were fed back to the generator
    (repair,) = gen.calls[1]
    assert repair.sql == "SELECT nme FROM customer"
    assert "nme" in repair.error


def test_unsafe_sql_is_never_executed_and_gets_repaired(engine, scripted):
    gen = scripted("DELETE FROM orders", "SELECT COUNT(*) FROM orders")
    ans = answer("how many orders?", gen, engine, "sqlite")
    assert ans.attempts[0].stage == "validate"
    assert ans.result.rows == [[4]]  # the DELETE never ran


def test_syntax_error_gets_repaired(engine, scripted):
    gen = scripted("SELECT FROM WHERE", "SELECT 1 AS one")
    ans = answer("one?", gen, engine, "sqlite")
    assert ans.attempts[0].stage == "validate"
    assert ans.result.rows == [[1]]


def test_gives_up_after_max_retries(engine, scripted):
    gen = scripted("SELECT bad1 FROM customer", "SELECT bad2 FROM customer", "SELECT bad3 FROM x")
    with pytest.raises(AnswerError) as exc:
        answer("?", gen, engine, "sqlite", max_retries=2)
    assert len(exc.value.attempts) == 3
    assert len(gen.calls) == 3


def test_row_limit_truncates(engine):
    res = run_query(engine, "SELECT * FROM orders", row_limit=2)
    assert len(res.rows) == 2 and res.truncated


def test_connection_is_read_only_even_if_validator_is_bypassed(engine):
    with pytest.raises(QueryError, match="readonly"):
        run_query(engine, "DELETE FROM orders", row_limit=10)
    assert run_query(engine, "SELECT COUNT(*) FROM orders", 10).rows == [[4]]


def test_long_query_times_out(db_path):
    from askdb.db import make_engine

    engine = make_engine(f"sqlite:///{db_path}", timeout_s=0.2)
    endless = (
        "WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n) SELECT COUNT(*) FROM n"
    )
    with pytest.raises(QueryError, match="timed out"):
        run_query(engine, endless, row_limit=10)
