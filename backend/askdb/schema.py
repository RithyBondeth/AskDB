"""Stage 1 (introspection) and stage 2 (schema linking)."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import Engine, inspect

from askdb.linking import TOP_K, SchemaIndex


@dataclass
class Column:
    name: str
    type: str
    primary_key: bool = False
    comment: str | None = None


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
            note = f" -- {_one_line(c.comment)}" if c.comment else ""
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


def link_tables(schema: Schema, question: str, top_k: int = TOP_K) -> list[Table]:
    """Pick the tables relevant to a question (keyword ranking only). The pipeline
    keeps a SchemaIndex per database instead, which can also use embeddings."""
    return SchemaIndex(schema).link(question, top_k)
