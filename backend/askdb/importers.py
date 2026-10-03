"""Turn uploaded files into SQLite databases AskDB can query.

Uploads are untrusted: SQLite files are checked before use, and CSVs are parsed
into a new database we create ourselves.
"""

from __future__ import annotations

import csv
import io
import re
import sqlite3
from pathlib import Path

SQLITE_MAGIC = b"SQLite format 3\x00"
SQLITE_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".db3"}
CSV_SUFFIXES = {".csv", ".tsv", ".txt"}


class UploadError(Exception):
    """The upload can't be used. The message is shown to the user."""


def sanitize_identifier(name: str, fallback: str) -> str:
    """'Order Date' -> 'order_date'. Plain snake_case names are easier for models to
    write correct SQL against than names that need quoting."""
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name.strip())
    name = re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower()
    if not name:
        name = fallback
    if name[0].isdigit():
        name = f"_{name}"
    return name


def _unique(name: str, taken: set[str]) -> str:
    candidate, n = name, 2
    while candidate in taken:
        candidate = f"{name}_{n}"
        n += 1
    taken.add(candidate)
    return candidate


def check_sqlite(path: Path) -> list[str]:
    """Validate an uploaded SQLite file and prepare it for read-only use.
    Returns its table names."""
    with path.open("rb") as f:
        if f.read(16) != SQLITE_MAGIC:
            raise UploadError("This isn't a SQLite database file.")
    try:
        conn = sqlite3.connect(path)
        try:
            conn.execute("PRAGMA trusted_schema = OFF")
            if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise UploadError("The database file is damaged.")
            # Our copy is opened read-only later; WAL mode would need write access.
            conn.execute("PRAGMA journal_mode = DELETE")
            tables = [
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' "
                    "AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
            ]
        finally:
            conn.close()
    except sqlite3.DatabaseError as e:
        raise UploadError(f"Couldn't open the database: {e}") from e
    if not tables:
        raise UploadError("The database has no tables.")
    return tables


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UploadError("Couldn't read the file's text encoding.")


def _infer_type(values: list[str]) -> str:
    present = [v for v in values if v != ""]
    if not present:
        return "TEXT"
    try:
        for v in present:
            int(v)
        return "INTEGER"
    except ValueError:
        pass
    try:
        for v in present:
            float(v)
        return "REAL"
    except ValueError:
        return "TEXT"


def _convert(value: str, sql_type: str):
    if value == "":
        return None
    if sql_type == "INTEGER":
        return int(value)
    if sql_type == "REAL":
        return float(value)
    return value


def csvs_to_sqlite(files: list[tuple[str, bytes]], dest: Path) -> list[str]:
    """Write each CSV as a table in a new SQLite database. Returns the table names."""
    taken: set[str] = set()
    tables: list[str] = []
    conn = sqlite3.connect(dest)
    try:
        for filename, data in files:
            text = _decode(data)
            sample = text[:20_000]
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            except csv.Error:
                dialect = csv.excel_tab if filename.lower().endswith(".tsv") else csv.excel
            rows = list(csv.reader(io.StringIO(text), dialect))
            rows = [r for r in rows if any(cell.strip() for cell in r)]
            if len(rows) < 2:
                raise UploadError(f"{filename}: needs a header row and at least one data row.")

            header, body = rows[0], rows[1:]
            width = len(header)
            body = [(r + [""] * width)[:width] for r in body]  # pad/trim ragged rows
            cols_taken: set[str] = set()
            columns = [
                _unique(sanitize_identifier(h, f"column_{i + 1}"), cols_taken)
                for i, h in enumerate(header)
            ]
            types = [_infer_type([r[i].strip() for r in body[:5000]]) for i in range(width)]
            # Values beyond the sample may not fit the guessed type; fall back to TEXT.
            for i, t in enumerate(types):
                if t != "TEXT":
                    try:
                        for r in body:
                            _convert(r[i].strip(), t)
                    except ValueError:
                        types[i] = "TEXT"

            table = _unique(sanitize_identifier(Path(filename).stem, "table"), taken)
            col_defs = ", ".join(f'"{c}" {t}' for c, t in zip(columns, types, strict=True))
            conn.execute(f'CREATE TABLE "{table}" ({col_defs})')
            placeholders = ", ".join("?" * width)
            conn.executemany(
                f'INSERT INTO "{table}" VALUES ({placeholders})',
                ([_convert(r[i].strip(), types[i]) for i in range(width)] for r in body),
            )
            tables.append(table)
        conn.commit()
    finally:
        conn.close()
    return tables
