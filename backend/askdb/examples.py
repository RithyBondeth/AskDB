"""Question/SQL examples built from a database's own schema.

The bundled sample has hand-written few-shot examples (askdb.prompts). Uploads
have none, so these are generated instead: simple questions over the upload's
real tables, each paired with SQL that has been validated and run. They show the
model the table and column names, the quoting, a join along a real foreign key,
and the dialect's date functions. The same questions double as the clickable
suggestions for an unfamiliar database.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

from sqlalchemy import Engine

from askdb.db import QueryError, run_query
from askdb.schema import Schema, Table
from askdb.validate import InvalidSQLError, UnsafeQueryError, validate_sql

_DATE_LIKE = re.compile(r"date|time|day|month|year|_at$|_on$", re.I)
_MONEY_LIKE = re.compile(r"revenue|amount|total|price|sales|cost|value|profit|spend|income", re.I)
_LABEL_LIKE = re.compile(r"name|title|category|product|region|country|city|type|status", re.I)
_NUMERIC_TYPES = ("INT", "REAL", "NUM", "DEC", "FLOAT", "DOUBLE")
_TEXT_TYPES = ("CHAR", "TEXT", "CLOB", "STRING")

# Generated examples that go into the prompt, and how many candidates to try
# running for them (each is one bounded query against the database).
MAX_EXAMPLES = 3
MAX_TRIES = 8


@dataclass
class Candidate:
    question: str
    sql: str | None  # None: a suggestion only, not worth showing as an example
    kind: str  # "join" | "date" | "group" | "count"


def _ranked(columns: list[str], prefer: re.Pattern[str]) -> list[str]:
    """Columns matching `prefer` first, otherwise in table order."""
    return sorted(columns, key=lambda c: 0 if prefer.search(c) else 1)


def _words(name: str) -> str:
    return name.replace("_", " ")


def _alias(name: str) -> str:
    return re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower() or "value"


def _total(measure: str) -> str:
    """'total amount', but not 'total Total'."""
    return _words(measure) if "total" in measure.lower() else f"total {_words(measure)}"


_PLAIN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def quoter(engine: Engine):
    """Quote an identifier only when it needs it, as the prompt asks the model to.
    (SQLAlchemy's own quote() also quotes every mixed-case name.)"""
    prep = engine.dialect.identifier_preparer

    def quote(name: str) -> str:
        if _PLAIN.match(name) and name.lower() not in prep.reserved_words:
            return name
        return prep.quote_identifier(name)

    return quote


@dataclass
class _Roles:
    dates: list[str]
    measures: list[str]  # numeric, not keys or dates; money-like first
    labels: list[str]  # text, not dates; name-like first


def _roles(t: Table) -> _Roles:
    dates = [c.name for c in t.columns if _DATE_LIKE.search(c.name)]
    keys = {c for fk in t.foreign_keys for c in fk.columns}
    measures = _ranked(
        [
            c.name
            for c in t.columns
            if any(k in c.type.upper() for k in _NUMERIC_TYPES)
            and not c.primary_key
            and not c.name.lower().endswith("id")
            and c.name not in keys
            and c.name not in dates
        ],
        _MONEY_LIKE,
    )
    labels = _ranked(
        [
            c.name
            for c in t.columns
            if (any(k in c.type.upper() for k in _TEXT_TYPES) or c.type == "")
            and c.name not in dates
        ],
        _LABEL_LIKE,
    )
    return _Roles(dates, measures, labels)


def candidates(schema: Schema, quote=lambda name: name) -> Iterator[Candidate]:
    """Every starter question for this schema, per table (widest tables first),
    then joins along foreign keys. `quote` quotes identifiers for the dialect."""
    q = quote
    by_name = {t.name: t for t in schema.tables}
    for t in sorted(schema.tables, key=lambda t: -len(t.columns)):
        r, name = _roles(t), _words(t.name)
        if r.labels and r.measures:
            label, m = r.labels[0], r.measures[0]
            total = _alias(_total(m))
            yield Candidate(
                f"Top 10 {_words(label)} by {_total(m)} in {name}",
                f"SELECT {q(label)}, SUM({q(m)}) AS {total}\n"
                f"FROM {q(t.name)}\n"
                f"GROUP BY {q(label)}\n"
                f"ORDER BY {total} DESC\n"
                f"LIMIT 10",
                "group",
            )
        if r.dates and r.measures and schema.dialect == "sqlite":
            d, m = r.dates[0], r.measures[0]
            month = f"strftime('%Y-%m', {q(d)})"
            yield Candidate(
                f"{_total(m).capitalize()} per month in {name}",
                f"SELECT {month} AS month, SUM({q(m)}) AS {_alias(_total(m))}\n"
                f"FROM {q(t.name)}\n"
                f"WHERE {month} IS NOT NULL\n"
                f"GROUP BY month\n"
                f"ORDER BY month",
                "date",
            )
        if len(r.labels) > 1 and r.measures:
            yield Candidate(
                f"{_total(r.measures[0]).capitalize()} by {_words(r.labels[1])} in {name}",
                None,
                "group",
            )
        yield Candidate(f"How many rows are in {name}?", None, "count")

    for child in schema.tables:
        for fk in child.foreign_keys:
            parent = by_name.get(fk.ref_table)
            if not parent or parent is child or len(fk.columns) != 1:
                continue
            labels = _roles(parent).labels
            if not labels:
                continue
            label = labels[0]
            count = f"{_alias(child.name)}_count"
            yield Candidate(
                f"Which {_words(parent.name)} {_words(label)} has the most "
                f"{_words(child.name)} rows?",
                f"SELECT p.{q(label)}, COUNT(*) AS {count}\n"
                f"FROM {q(child.name)} c\n"
                f"JOIN {q(parent.name)} p ON p.{q(fk.ref_columns[0])} = c.{q(fk.columns[0])}\n"
                f"GROUP BY p.{q(label)}\n"
                f"ORDER BY {count} DESC\n"
                f"LIMIT 10",
                "join",
            )


def suggest_questions(schema: Schema, limit: int = 6) -> list[str]:
    """Simple starter questions built from the schema, so an unfamiliar database
    has something to click."""
    seen: set[str] = set()
    out = [c.question for c in candidates(schema)]
    return [x for x in out if not (x in seen or seen.add(x))][:limit]


def schema_examples(
    schema: Schema, engine: Engine, limit: int = MAX_EXAMPLES
) -> list[tuple[str, str]]:
    """Up to `limit` examples whose SQL passes validation and returns data:
    one of each kind first (a join, a monthly series, a group-by), then more."""
    pool = [c for c in candidates(schema, quoter(engine)) if c.sql]
    picked: list[Candidate] = []
    tries = 0

    def first_working(options: list[Candidate]) -> Candidate | None:
        nonlocal tries
        for c in options:
            if tries == MAX_TRIES:
                return None
            tries += 1
            if _works(c.sql, engine, schema.dialect):
                return c
        return None

    for kind in ("join", "date", "group"):
        if len(picked) < limit and (c := first_working([c for c in pool if c.kind == kind])):
            picked.append(c)
    while len(picked) < limit and (c := first_working([c for c in pool if c not in picked])):
        picked.append(c)
    return [(c.question, c.sql) for c in picked]


def _works(sql: str, engine: Engine, dialect: str) -> bool:
    try:
        validate_sql(sql, dialect)
        rows = run_query(engine, sql, row_limit=5).rows
    except (InvalidSQLError, UnsafeQueryError, QueryError):
        return False
    return any(r and r[0] is not None for r in rows)
