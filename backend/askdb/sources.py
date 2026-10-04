"""The databases AskDB can answer from: the configured sample plus uploads.

Each upload is stored as `<id>.sqlite` with a `<id>.json` metadata file beside it
in `upload_dir`, so uploads survive restarts.
"""

from __future__ import annotations

import datetime as dt
import hashlib
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
# The browser's random id (see frontend/src/lib/owner.ts). There are no accounts:
# whoever holds the id owns the uploads made with it.
_OWNER = re.compile(r"^[A-Za-z0-9_-]{16,128}$")


def valid_owner(owner: str | None) -> bool:
    return bool(owner and _OWNER.match(owner))


def _owner_hash(owner: str | None) -> str:
    """Stored instead of the id itself, so the metadata files don't hold anything
    that would let someone act as that browser. "" = no owner (shared)."""
    return hashlib.sha256(owner.encode()).hexdigest() if valid_owner(owner) else ""


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
    # Hash of the uploading browser's id; "" for uploads visible to everyone
    # (sample, uploads made before scoping existed, or made from the CLI/tests).
    owner: str = ""

    def to_dict(self) -> dict:
        """What the API returns: everything but the owner hash."""
        d = asdict(self)
        d.pop("owner")
        return d

    def visible_to(self, owner: str | None) -> bool:
        return not self.owner or self.owner == _owner_hash(owner)


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

    def get(self, source_id: str | None, owner: str | None = None) -> AskDB:
        """The pipeline for a database. Raises KeyError if it doesn't exist or
        belongs to another browser (the two look the same to the caller)."""
        if not source_id or source_id == SAMPLE_ID:
            return self.sample()
        info = self._info(source_id, owner)
        with self._lock:
            if source_id not in self._cache:
                # Share one Anthropic client across databases.
                client = self._cache[SAMPLE_ID].client if SAMPLE_ID in self._cache else None
                self._cache[source_id] = AskDB.for_sqlite_file(
                    str(self._db_path(info.id)), self.settings, client
                )
            return self._cache[source_id]

    def list(self, owner: str | None = None) -> list[SourceInfo]:
        """The sample plus the uploads `owner` can see."""
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
        uploads = [u for u in self._uploads() if u.visible_to(owner)]
        return items + sorted(uploads, key=lambda s: s.created_at, reverse=True)

    def suggestions(self, source_id: str | None, owner: str | None = None) -> list[str]:
        if not source_id or source_id == SAMPLE_ID:
            if "chinook" in self.settings.database_url:
                return SAMPLE_SUGGESTIONS
        return suggest_questions(self.get(source_id, owner).schema)

    # ------------------------------------------------------------ writing

    def add(
        self, files: list[tuple[str, bytes]], name: str | None = None, owner: str | None = None
    ) -> SourceInfo:
        """Create a database from one SQLite file or one or more CSV files.

        With an `owner`, only that browser can see, query, or delete it. Without
        one it is visible to everyone; the API always passes one.
        """
        if not self.settings.allow_uploads:
            raise UploadError("Uploads are turned off on this server.")
        if not files:
            raise UploadError("Choose a file to upload.")
        uploads = self._uploads()
        mine = _owner_hash(owner)
        if sum(u.owner == mine for u in uploads) >= self.settings.max_uploads:
            raise UploadError(
                f"Upload limit reached ({self.settings.max_uploads}). Delete one first."
            )
        if len(uploads) >= self.settings.max_total_uploads:
            raise UploadError("This server is full. Try again later, or run AskDB yourself.")
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
            owner=mine,
        )
        self._meta_path(source_id).write_text(json.dumps(asdict(info)))
        return info

    def delete(self, source_id: str, owner: str | None = None) -> None:
        if source_id == SAMPLE_ID:
            raise UploadError("The sample database can't be deleted.")
        self._info(source_id, owner)
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

    def _uploads(self) -> list[SourceInfo]:
        """Every upload, whoever owns it."""
        if not self.dir.exists():
            return []
        out = []
        for meta in self.dir.glob("*.json"):
            try:
                out.append(SourceInfo(**json.loads(meta.read_text())))
            except (ValueError, TypeError):
                continue
        return out

    def _info(self, source_id: str, owner: str | None) -> SourceInfo:
        if not _ID.match(source_id):  # also rules out path tricks like "../x"
            raise KeyError(source_id)
        meta = self._meta_path(source_id)
        if not meta.exists():
            raise KeyError(source_id)
        info = SourceInfo(**json.loads(meta.read_text()))
        if not info.visible_to(owner):
            raise KeyError(source_id)
        return info

    def _db_path(self, source_id: str) -> Path:
        return self.dir / f"{source_id}.sqlite"

    def _meta_path(self, source_id: str) -> Path:
        return self.dir / f"{source_id}.json"
