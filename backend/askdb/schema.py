"""Stage 1 (introspection) and stage 2 (schema linking)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

from askdb.linking import TOP_K, SchemaIndex

log = logging.getLogger("askdb.schema")


@dataclass
class Column:
    name: str
    type: str
    primary_key: bool = False
    comment: str | None = None
    # A few of the column's most common values, shown to the model so it writes
    # 'USA' rather than guessing 'United States' (see sample_values()).
    samples: list[str] = field(default_factory=list)


@dataclass
class ForeignKey:
    columns: list[str]
    ref_table: str
    ref_columns: list[str]


@dataclass
class Table:
    name: str
    columns: list[Column]
    foreign_keys: list[ForeignKey] = field(default_factory=list)
    comment: str | None = None

    def ddl(self) -> str:
        lines = []
        for c in self.columns:
            pk = " PRIMARY KEY" if c.primary_key else ""
            notes = [_one_line(c.comment)] if c.comment else []
            if c.samples:
                notes.append("e.g. " + ", ".join(_sql_string(v) for v in c.samples))
            note = f" -- {'; '.join(notes)}" if notes else ""
            lines.append(f"  {c.name} {c.type}{pk}{note}")
        for fk in self.foreign_keys:
            lines.append(
                f"  FOREIGN KEY ({', '.join(fk.columns)}) "
                f"REFERENCES {fk.ref_table}({', '.join(fk.ref_columns)})"
            )
        head = f"-- {_one_line(self.comment)}\n" if self.comment else ""
        # Comments go after the comma so the DDL stays valid SQL.
        body = ""
        for i, line in enumerate(lines):
            sep = "," if i < len(lines) - 1 else ""
            code, _, note = line.partition(" -- ")
            body += f"{code}{sep}" + (f" -- {note}" if note else "") + "\n"
        return f"{head}CREATE TABLE {self.name} (\n{body});"


def _one_line(text: str, limit: int = 200) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


@dataclass
class Schema:
    dialect: str
    tables: list[Table]

    def ddl(self, tables: list[Table] | None = None) -> str:
        return "\n\n".join(t.ddl() for t in (tables if tables is not None else self.tables))

    def to_dict(self) -> dict:
        return {
            "dialect": self.dialect,
            "tables": [
                {
                    "name": t.name,
                    "columns": [
                        {"name": c.name, "type": c.type, "primary_key": c.primary_key}
                        for c in t.columns
                    ],
                }
                for t in self.tables
            ],
        }


def introspect(engine: Engine) -> Schema:
    insp = inspect(engine)
    tables = []
    for name in sorted(insp.get_table_names()):
        pk = set(insp.get_pk_constraint(name).get("constrained_columns") or [])
        columns = [
            Column(c["name"], str(c["type"]), c["name"] in pk, c.get("comment") or None)
            for c in insp.get_columns(name)
        ]
        fks = [
            ForeignKey(fk["constrained_columns"], fk["referred_table"], fk["referred_columns"])
            for fk in insp.get_foreign_keys(name)
        ]
        tables.append(Table(name, columns, fks, _table_comment(insp, name)))
    return Schema(dialect=engine.dialect.name, tables=tables)


def _table_comment(insp, name: str) -> str | None:
    try:
        return insp.get_table_comment(name).get("text") or None
    except NotImplementedError:  # SQLite has no comments
        return None


# Sample values. Text columns get them only when they look categorical (few
# distinct values: countries, statuses, genres), dates get one (to show the
# storage format), and keys, secrets and personal contact details never do: they
# wouldn't help write SQL, and needn't be sent to the model.
_TEXT = ("CHAR", "TEXT", "CLOB", "STRING", "ENUM")
_TEMPORAL = ("DATE", "TIME")
_SKIP = re.compile(
    r"pass(word|wd)?|secret|token|hash|salt|api_?key|ssn"  # secrets
    r"|e_?mail|phone|fax|address|postal|zip|birth|dob",  # personal contact details
    re.I,
)
SAMPLE_ROWS = 1000  # rows read per column, so big tables stay cheap
MAX_DISTINCT = 50  # more distinct values than this in those rows: not categorical
MAX_SAMPLE_LENGTH = 40


def sample_values(engine: Engine, table: Table, per_column: int) -> None:
    """Fill in `samples` on the table's columns: for categorical text columns, the
    most common values among the first SAMPLE_ROWS rows (most common first, ties
    alphabetical, so the prompt stays the same between questions); for date and
    time columns, one value, to show the format. A column that can't be read just
    gets no samples."""
    if per_column <= 0:
        return
    keys = {c for fk in table.foreign_keys for c in fk.columns}
    quote = engine.dialect.identifier_preparer.quote
    with engine.connect() as conn:
        for c in table.columns:
            kind = c.type.upper()
            temporal = any(k in kind for k in _TEMPORAL)
            if (
                c.primary_key
                or c.name in keys
                or _SKIP.search(c.name)
                or not (temporal or any(k in kind for k in _TEXT))
            ):
                continue
            col, tbl = quote(c.name), quote(table.name)
            sql = (
                f"SELECT v, COUNT(*) AS n FROM (SELECT {col} AS v FROM {tbl} "
                f"LIMIT {SAMPLE_ROWS}) s WHERE v IS NOT NULL "
                f"GROUP BY v ORDER BY n DESC, v LIMIT {MAX_DISTINCT + 1}"
            )
            try:
                rows = conn.execute(text(sql)).all()
            except SQLAlchemyError as e:
                log.debug("No sample values for %s.%s: %s", table.name, c.name, e)
                continue
            if not temporal and len(rows) > MAX_DISTINCT:
                continue  # names, titles, free text: values wouldn't help
            usable = [
                v
                for v, _ in rows
                if isinstance(v, str) and 0 < len(v) <= MAX_SAMPLE_LENGTH and "\n" not in v
            ]
            c.samples = usable[: 1 if temporal else per_column]


def link_tables(schema: Schema, question: str, top_k: int = TOP_K) -> list[Table]:
    """Pick the tables relevant to a question (keyword ranking only). The pipeline
    keeps a SchemaIndex per database instead, which can also use embeddings."""
    return SchemaIndex(schema).link(question, top_k)
