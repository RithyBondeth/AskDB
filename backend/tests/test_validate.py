"""Prove the read-only guard works."""

import pytest

from askdb.validate import InvalidSQLError, UnsafeQueryError, is_safe, validate_sql

READS = [
    "SELECT 1",
    "SELECT name FROM customer WHERE country = 'UK'",
    "select a from t union select b from u",
    "SELECT a FROM t INTERSECT SELECT a FROM u",
    "SELECT a FROM t EXCEPT SELECT a FROM u",
    "WITH big AS (SELECT * FROM orders WHERE total > 10) SELECT COUNT(*) FROM big",
    "SELECT c.name, SUM(o.total) FROM customer c JOIN orders o ON o.customer_id = c.id GROUP BY 1",
    "SELECT * FROM t WHERE note = 'please DROP TABLE t'",  # keywords inside strings are data
    "SELECT 1;",  # a trailing semicolon is still one statement
]

WRITES = [
    "INSERT INTO customer VALUES (4, 'Eve', 'NZ')",
    "UPDATE customer SET name = 'x'",
    "DELETE FROM orders",
    "DROP TABLE customer",
    "ALTER TABLE customer ADD COLUMN x INT",
    "CREATE TABLE x (id INT)",
    "CREATE TABLE x AS SELECT * FROM customer",
    "REPLACE INTO customer VALUES (1, 'x', 'y')",
    "PRAGMA writable_schema = 1",
    "ATTACH DATABASE 'other.db' AS other",
    "VACUUM",
    "SELECT * INTO backup FROM customer",
    "SELECT * FROM customer FOR UPDATE",
    "SELECT 1; DROP TABLE customer",  # stacked statement
    "SELECT 1; SELECT 2",  # more than one statement, even if both are reads
    "BEGIN TRANSACTION",
]


@pytest.mark.parametrize("sql", READS)
def test_allows_reads(sql):
    assert is_safe(sql, "sqlite")


@pytest.mark.parametrize("sql", WRITES)
def test_blocks_writes(sql):
    assert not is_safe(sql, "sqlite")
    with pytest.raises((UnsafeQueryError, InvalidSQLError)):
        validate_sql(sql, "sqlite")


def test_postgres_writable_cte_is_blocked():
    sql = "WITH gone AS (DELETE FROM orders RETURNING *) SELECT * FROM gone"
    with pytest.raises(UnsafeQueryError):
        validate_sql(sql, "postgres")


def test_syntax_error_is_reported_as_invalid():
    with pytest.raises(InvalidSQLError):
        validate_sql("SELECT FROM WHERE", "sqlite")


def test_empty_input_is_rejected():
    with pytest.raises(UnsafeQueryError):
        validate_sql("   ", "sqlite")
