"""The databases AskDB can answer from: the configured sample plus uploads.

Each upload is stored as `<id>.sqlite` with a `<id>.json` metadata file beside it
in `upload_dir`, so uploads survive restarts.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import threading
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

import anthropic

from askdb.config import Settings, get_settings
from askdb.importers import (
    CSV_SUFFIXES,
    SQLITE_SUFFIXES,
    UploadError,
    check_sqlite,
    csvs_to_sqlite,
)
from askdb.pipeline import AskDB
from askdb.schema import Schema

SAMPLE_ID = "sample"
_ID = re.compile(r"^[0-9a-f]{32}$")

# Curated questions for the bundled Chinook sample.
SAMPLE_SUGGESTIONS = [
    "Which artist has the most albums?",
    "Total revenue by country, top 10",
    "Revenue per month in 2013",
    "Who are the top 5 customers by total spend?",
    "How many tracks are in each genre?",
    "What was our revenue last quarter?",
]


@dataclass
class SourceInfo:
    id: str
    name: str
    kind: str  # "sample" | "sqlite" | "csv"
    tables: int
    size_bytes: int
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)


_DATE_LIKE = re.compile(r"date|time|day|month|year|_at$|_on$", re.I)
_MONEY_LIKE = re.compile(r"revenue|amount|total|price|sales|cost|value|profit|spend|income", re.I)
_LABEL_LIKE = re.compile(r"name|title|category|product|region|country|city|type|status", re.I)
_NUMERIC_TYPES = ("INT", "REAL", "NUM", "DEC", "FLOAT", "DOUBLE")


def _ranked(columns: list[str], prefer: re.Pattern[str]) -> list[str]:
    """Columns matching `prefer` first, otherwise in table order."""
    return sorted(columns, key=lambda c: 0 if prefer.search(c) else 1)


def suggest_questions(schema: Schema, limit: int = 6) -> list[str]:
    """Simple starter questions built from the schema, so an unfamiliar database
    has something to click."""
    out: list[str] = []
    for t in sorted(schema.tables, key=lambda t: -len(t.columns)):
        name = t.name.replace("_", " ")
        dates = [c.name for c in t.columns if _DATE_LIKE.search(c.name)]
        nums = _ranked(
            [
                c.name
                for c in t.columns
                if any(k in c.type.upper() for k in _NUMERIC_TYPES)
                and not c.primary_key
                and not c.name.lower().endswith("id")
                and c.name not in dates
            ],
            _MONEY_LIKE,
        )
        labels = _ranked(
            [
                c.name
                for c in t.columns
                if ("CHAR" in c.type.upper() or "TEXT" in c.type.upper() or c.type == "")
                and c.name not in dates
            ],
            _LABEL_LIKE,
        )
        measure = nums[0].replace("_", " ") if nums else ""
        if labels and nums:
            out.append(f"Top 10 {labels[0].replace('_', ' ')} by total {measure} in {name}")
        if dates and nums:
            out.append(f"Total {measure} per month in {name}")
        if len(labels) > 1 and nums:
            out.append(f"Total {measure} by {labels[1].replace('_', ' ')} in {name}")
        out.append(f"How many rows are in {name}?")
    seen: set[str] = set()
    return [q for q in out if not (q in seen or seen.add(q))][:limit]


class SourceRegistry:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.dir = Path(self.settings.upload_dir)
        self._cache: dict[str, AskDB] = {}
        self._lock = threading.Lock()
        self._client: anthropic.Anthropic | None = None

    # ------------------------------------------------------------ reading

    def sample(self) -> AskDB:
        with self._lock:
            if SAMPLE_ID not in self._cache:
                self._cache[SAMPLE_ID] = AskDB.from_settings(self.settings)
            return self._cache[SAMPLE_ID]

    def get(self, source_id: str | None) -> AskDB:
        if not source_id or source_id == SAMPLE_ID:
            return self.sample()
        info = self._info(source_id)  # raises KeyError if unknown
        with self._lock:
            if source_id not in self._cache:
                # Share one Anthropic client across databases.
                client = self._cache[SAMPLE_ID].client if SAMPLE_ID in self._cache else None
                self._cache[source_id] = AskDB.for_sqlite_file(
                    str(self._db_path(info.id)), self.settings, client
                )
            return self._cache[source_id]

    def list(self) -> list[SourceInfo]:
        sample = self.sample()
        items = [
            SourceInfo(
                id=SAMPLE_ID,
                name="Chinook (sample)"
                if "chinook" in self.settings.database_url
                else "Default database",
                kind="sample",
                tables=len(sample.schema.tables),
                size_bytes=0,
                created_at="",
            )
        ]
        if self.dir.exists():
            uploads = []
            for meta in self.dir.glob("*.json"):
                try:
                    uploads.append(SourceInfo(**json.loads(meta.read_text())))
                except (ValueError, TypeError):
                    continue
            items += sorted(uploads, key=lambda s: s.created_at, reverse=True)
        return items

    def suggestions(self, source_id: str | None) -> list[str]:
        if not source_id or source_id == SAMPLE_ID:
            if "chinook" in self.settings.database_url:
                return SAMPLE_SUGGESTIONS
        return suggest_questions(self.get(source_id).schema)

    # ------------------------------------------------------------ writing

    def add(self, files: list[tuple[str, bytes]], name: str | None = None) -> SourceInfo:
        """Create a database from one SQLite file or one or more CSV files."""
        if not self.settings.allow_uploads:
            raise UploadError("Uploads are turned off on this server.")
        if not files:
            raise UploadError("Choose a file to upload.")
        if len(self.list()) - 1 >= self.settings.max_uploads:
            raise UploadError(
                f"Upload limit reached ({self.settings.max_uploads}). Delete one first."
            )
        total = sum(len(data) for _, data in files)
        if total > self.settings.max_upload_mb * 1024 * 1024:
            raise UploadError(f"Files are larger than {self.settings.max_upload_mb} MB.")

        suffixes = {Path(f).suffix.lower() for f, _ in files}
        if suffixes <= SQLITE_SUFFIXES:
            if len(files) != 1:
                raise UploadError("Upload one SQLite file at a time.")
            kind = "sqlite"
        elif suffixes <= CSV_SUFFIXES:
            kind = "csv"
        else:
            raise UploadError(
                "Unsupported file type. Upload a SQLite file (.db, .sqlite, .sqlite3) or CSV files."
            )

        self.dir.mkdir(parents=True, exist_ok=True)
        source_id = uuid.uuid4().hex
        db_path = self._db_path(source_id)
        try:
            if kind == "sqlite":
                db_path.write_bytes(files[0][1])
                tables = check_sqlite(db_path)
            else:
                tables = csvs_to_sqlite(files, db_path)
        except Exception:
            db_path.unlink(missing_ok=True)
            raise

        default_name = Path(files[0][0]).stem if len(files) == 1 else f"{len(files)} CSV files"
        info = SourceInfo(
            id=source_id,
            name=(name or default_name).strip()[:80] or "Untitled",
            kind=kind,
            tables=len(tables),
            size_bytes=db_path.stat().st_size,
            created_at=dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        )
        self._meta_path(source_id).write_text(json.dumps(info.to_dict()))
        return info

    def delete(self, source_id: str) -> None:
        if source_id == SAMPLE_ID:
            raise UploadError("The sample database can't be deleted.")
        self._info(source_id)
        with self._lock:
            db = self._cache.pop(source_id, None)
        if db is not None:
            db.engine.dispose()
        self._db_path(source_id).unlink(missing_ok=True)
        self._meta_path(source_id).unlink(missing_ok=True)

    def clear(self) -> None:
        """Remove every upload (used by tests)."""
        with self._lock:
            for key in [k for k in self._cache if k != SAMPLE_ID]:
                self._cache.pop(key).engine.dispose()
        shutil.rmtree(self.dir, ignore_errors=True)

    # ------------------------------------------------------------ helpers

    def _info(self, source_id: str) -> SourceInfo:
        if not _ID.match(source_id):  # also rules out path tricks like "../x"
            raise KeyError(source_id)
        meta = self._meta_path(source_id)
        if not meta.exists():
            raise KeyError(source_id)
        return SourceInfo(**json.loads(meta.read_text()))

    def _db_path(self, source_id: str) -> Path:
        return self.dir / f"{source_id}.sqlite"

    def _meta_path(self, source_id: str) -> Path:
        return self.dir / f"{source_id}.json"
