"""Stage 4: the read-only safety gate. Model output never runs unchecked."""

from __future__ import annotations

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError


class UnsafeQueryError(Exception):
    """The query is not a single read-only statement."""


class InvalidSQLError(Exception):
    """The query could not be parsed."""


# Anything that writes, changes schema, or touches session/connection state.
FORBIDDEN = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Drop,
    exp.Alter,
    exp.Create,
    exp.TruncateTable,
    exp.Command,
    exp.Pragma,
    exp.Attach,
    exp.Detach,
    exp.Transaction,
    exp.Commit,
    exp.Rollback,
    exp.Set,
    exp.Use,
    exp.Copy,
    exp.Grant,
    exp.Into,  # SELECT ... INTO new_table
    exp.Lock,  # SELECT ... FOR UPDATE
)

# Top-level statements that only read.
READ_ONLY_ROOTS = (exp.Select, exp.SetOperation)  # SetOperation = UNION / INTERSECT / EXCEPT


def validate_sql(sql: str, dialect: str) -> str:
    """Return the query (stripped) if it is one read-only statement, else raise."""
    try:
        statements = [s for s in sqlglot.parse(sql, read=dialect) if s is not None]
    except ParseError as e:
        raise InvalidSQLError(str(e).split("\n")[0]) from e

    if len(statements) != 1:
        raise UnsafeQueryError(f"Expected exactly one statement, got {len(statements)}.")
    tree = statements[0]

    if not isinstance(tree, READ_ONLY_ROOTS):
        raise UnsafeQueryError(f"Only SELECT queries are allowed (got {tree.key.upper()}).")
    for node_type in FORBIDDEN:
        if tree.find(node_type):
            raise UnsafeQueryError(f"Query contains a forbidden {node_type.__name__} clause.")

    return sql.strip().rstrip(";").strip()


def is_safe(sql: str, dialect: str) -> bool:
    try:
        validate_sql(sql, dialect)
    except (UnsafeQueryError, InvalidSQLError):
        return False
    return True
