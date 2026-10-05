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

# Functions a SELECT can call that act instead of read: change session settings,
# sleep, signal or lock other sessions, read server files, run SQL passed as a
# string, write large objects, or load code. Matched by name, case-insensitively
# and whatever the schema prefix, so `pg_catalog.pg_sleep` is caught too.
FORBIDDEN_FUNCTIONS = frozenset(
    {
        # Postgres
        "set_config",  # e.g. turning off default_transaction_read_only
        "nextval",
        "setval",
        "query_to_xml",  # these four run the SQL string they're given
        "query_to_xmlschema",
        "query_to_xml_and_xmlschema",
        "cursor_to_xml",
        "pg_notify",
        "pg_promote",
        "pg_export_snapshot",
        "pg_import_system_collations",
        "txid_current",  # assigns a transaction id
        "pg_current_xact_id",
        # SQLite (and its common shell/extension functions)
        "load_extension",
        "readfile",
        "writefile",
        "edit",
        "fts3_tokenizer",
    }
)
FORBIDDEN_FUNCTION_PREFIXES = (
    "pg_sleep",  # pg_sleep, pg_sleep_for, pg_sleep_until
    "pg_terminate_",
    "pg_cancel_",
    "pg_reload_",
    "pg_rotate_",
    "pg_log_",
    "pg_read_",  # pg_read_file, pg_read_binary_file
    "pg_ls_",
    "pg_stat_file",
    "pg_file_",  # adminpack writes
    "pg_advisory",
    "pg_try_advisory",
    "pg_create_",  # restore points, replication slots
    "pg_drop_",
    "pg_replication_",
    "pg_switch_",
    "pg_backup_",
    "pg_logical_",
    "pg_wal_",
    "lo_",  # large objects: lo_import, lo_export, lo_unlink, ...
    "dblink",
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
    for func in tree.find_all(exp.Func):
        name = _function_name(func)
        if name in FORBIDDEN_FUNCTIONS or name.startswith(FORBIDDEN_FUNCTION_PREFIXES):
            raise UnsafeQueryError(f"Query calls a forbidden function: {name}().")

    return sql.strip().rstrip(";").strip()


def _function_name(func: exp.Func) -> str:
    """The called name: as written for functions sqlglot doesn't know, else its own."""
    return (func.name if isinstance(func, exp.Anonymous) else func.sql_name()).lower()


def is_safe(sql: str, dialect: str) -> bool:
    try:
        validate_sql(sql, dialect)
    except (UnsafeQueryError, InvalidSQLError):
        return False
    return True
