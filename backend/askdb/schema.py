"""Stage 1 (introspection) and stage 2 (schema linking)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import Engine, inspect


@dataclass
class Column:
    name: str
    type: str
    primary_key: bool = False


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

    def ddl(self) -> str:
        lines = []
        for c in self.columns:
            pk = " PRIMARY KEY" if c.primary_key else ""
            lines.append(f"  {c.name} {c.type}{pk}")
        for fk in self.foreign_keys:
            lines.append(
                f"  FOREIGN KEY ({', '.join(fk.columns)}) "
                f"REFERENCES {fk.ref_table}({', '.join(fk.ref_columns)})"
            )
        return f"CREATE TABLE {self.name} (\n" + ",\n".join(lines) + "\n);"


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
            Column(c["name"], str(c["type"]), c["name"] in pk) for c in insp.get_columns(name)
        ]
        fks = [
            ForeignKey(fk["constrained_columns"], fk["referred_table"], fk["referred_columns"])
            for fk in insp.get_foreign_keys(name)
        ]
        tables.append(Table(name, columns, fks))
    return Schema(dialect=engine.dialect.name, tables=tables)


# Small schemas fit in the prompt whole; beyond this, link to relevant tables.
FULL_SCHEMA_MAX_TABLES = 15


def link_tables(schema: Schema, question: str, top_k: int = 8) -> list[Table]:
    """Pick the tables relevant to a question.

    v1 sends the whole schema when it is small. For larger schemas this uses a
    lexical score over table/column names plus foreign-key neighbours, as a
    stand-in for the embedding-based retrieval planned for v2.
    """
    if len(schema.tables) <= FULL_SCHEMA_MAX_TABLES:
        return schema.tables

    words = {_stem(w) for w in re.findall(r"[a-z]+", question.lower())}
    scored = []
    for t in schema.tables:
        names = [t.name, *(c.name for c in t.columns)]
        tokens = {_stem(tok) for n in names for tok in _split_identifier(n)}
        score = 3 * len(words & {_stem(tok) for tok in _split_identifier(t.name)})
        score += len(words & tokens)
        scored.append((score, t))
    picked = [t for s, t in sorted(scored, key=lambda x: -x[0]) if s > 0][:top_k]

    by_name = {t.name: t for t in schema.tables}
    for t in list(picked):  # pull in direct FK targets so joins are possible
        for fk in t.foreign_keys:
            ref = by_name.get(fk.ref_table)
            if ref and ref not in picked:
                picked.append(ref)
    return picked or schema.tables


def _split_identifier(name: str) -> list[str]:
    parts = re.sub(r"([a-z])([A-Z])", r"\1 \2", name).replace("_", " ").lower().split()
    return parts


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word
