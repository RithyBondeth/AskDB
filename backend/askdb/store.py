"""Saved answers and feedback, kept in a small SQLite file on the server.

Every answered question is saved for the browser that asked it (its owner id),
so the history survives clearing the browser and follows the owner id to another
device. Saved answers can be shared by link. Thumbs up/down on an answer, with
the corrected SQL when the user fixed it, build a dataset that can be exported
as eval cases and reused as few-shot examples.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_ID = re.compile(r"^[0-9a-f]{32}$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS answers (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,          -- sha256 of the browser's owner id
    database TEXT NOT NULL,
    question TEXT NOT NULL,
    sql TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    response TEXT NOT NULL,       -- the AskResponse JSON, rows included
    shared INTEGER NOT NULL DEFAULT 0,
    rating INTEGER,               -- latest feedback: 1, -1, or NULL
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS answers_owner ON answers (owner, database, created_at);

CREATE TABLE IF NOT EXISTS feedback (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    answer_id TEXT,
    database TEXT NOT NULL,
    question TEXT NOT NULL,
    sql TEXT NOT NULL,            -- what the model wrote
    corrected_sql TEXT,           -- what the user changed it to, if they did
    rating INTEGER NOT NULL,      -- 1 or -1
    comment TEXT,
    provider TEXT,
    model TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS feedback_db ON feedback (database, owner);
"""


def owner_hash(owner: str) -> str:
    return hashlib.sha256(owner.encode()).hexdigest()


def _now() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


@dataclass
class AnswerSummary:
    id: str
    database: str
    question: str
    created_at: str
    shared: bool
    rating: int | None


@dataclass
class Example:
    """A question and the SQL that answers it, from feedback."""

    question: str
    sql: str


class Store:
    def __init__(self, path: Path, max_answers_per_owner: int = 500):
        self.path = Path(path)
        self.max_answers = max_answers_per_owner
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def _exec(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            cur = self._conn.execute(sql, params)
            rows = cur.fetchall()
            self._conn.commit()
            return rows

    # ------------------------------------------------------------ answers

    def save_answer(self, owner: str, database: str, response: dict[str, Any]) -> str:
        """Save an answer for `owner`; returns its id. Keeps the newest
        `max_answers_per_owner` answers per owner."""
        answer_id = uuid.uuid4().hex
        mine = owner_hash(owner)
        self._exec(
            "INSERT INTO answers (id, owner, database, question, sql, provider, model, "
            "response, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                answer_id,
                mine,
                database,
                response["question"],
                response["sql"],
                response["provider"],
                response["model"],
                json.dumps(response, default=str),
                _now(),
            ),
        )
        self._exec(
            "DELETE FROM answers WHERE owner = ? AND id NOT IN "
            "(SELECT id FROM answers WHERE owner = ? ORDER BY created_at DESC, rowid DESC "
            "LIMIT ?)",
            (mine, mine, self.max_answers),
        )
        return answer_id

    def update_answer(self, owner: str, answer_id: str, changes: dict[str, Any]) -> None:
        """Merge `changes` into a saved answer's response (e.g. its summary)."""
        row = self._row(owner, answer_id)
        if row is None:
            return
        response = json.loads(row["response"]) | changes
        self._exec(
            "UPDATE answers SET response = ?, sql = ? WHERE id = ?",
            (json.dumps(response, default=str), response["sql"], answer_id),
        )

    def list_answers(
        self, owner: str, database: str | None = None, limit: int = 50
    ) -> list[AnswerSummary]:
        query = (
            "SELECT id, database, question, created_at, shared, rating FROM answers WHERE owner = ?"
        )
        params: tuple = (owner_hash(owner),)
        if database:
            query += " AND database = ?"
            params += (database,)
        query += " ORDER BY created_at DESC, rowid DESC LIMIT ?"
        rows = self._exec(query, params + (limit,))
        return [
            AnswerSummary(
                id=r["id"],
                database=r["database"],
                question=r["question"],
                created_at=r["created_at"],
                shared=bool(r["shared"]),
                rating=r["rating"],
            )
            for r in rows
        ]

    def get_answer(self, owner: str | None, answer_id: str) -> dict[str, Any] | None:
        """A saved answer, if `owner` saved it or it has been shared."""
        if not _ID.match(answer_id):
            return None
        rows = self._exec("SELECT * FROM answers WHERE id = ?", (answer_id,))
        if not rows:
            return None
        row = rows[0]
        if not row["shared"] and (not owner or row["owner"] != owner_hash(owner)):
            return None
        return self._full(row)

    def share_answer(self, owner: str, answer_id: str, shared: bool = True) -> bool:
        if self._row(owner, answer_id) is None:
            return False
        self._exec("UPDATE answers SET shared = ? WHERE id = ?", (int(shared), answer_id))
        return True

    def delete_answers(
        self, owner: str, answer_id: str | None = None, database: str | None = None
    ) -> int:
        """Delete one answer, or every answer for a database (or all of the owner's)."""
        query, params = "DELETE FROM answers WHERE owner = ?", (owner_hash(owner),)
        if answer_id:
            query += " AND id = ?"
            params += (answer_id,)
        if database:
            query += " AND database = ?"
            params += (database,)
        with self._lock:
            cur = self._conn.execute(query, params)
            self._conn.commit()
            return cur.rowcount

    def delete_database(self, database: str) -> None:
        """Forget everything about a deleted database."""
        self._exec("DELETE FROM answers WHERE database = ?", (database,))
        self._exec("DELETE FROM feedback WHERE database = ?", (database,))

    def _row(self, owner: str, answer_id: str) -> sqlite3.Row | None:
        if not _ID.match(answer_id):
            return None
        rows = self._exec(
            "SELECT * FROM answers WHERE id = ? AND owner = ?", (answer_id, owner_hash(owner))
        )
        return rows[0] if rows else None

    @staticmethod
    def _full(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "database": row["database"],
            "created_at": row["created_at"],
            "shared": bool(row["shared"]),
            "rating": row["rating"],
            "response": json.loads(row["response"]),
        }

    # ------------------------------------------------------------ feedback

    def add_feedback(
        self,
        owner: str,
        database: str,
        question: str,
        sql: str,
        rating: int,
        corrected_sql: str | None = None,
        comment: str | None = None,
        answer_id: str | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> str:
        """Record a rating. A newer rating for the same answer replaces the older one."""
        mine = owner_hash(owner)
        if answer_id:
            self._exec("DELETE FROM feedback WHERE owner = ? AND answer_id = ?", (mine, answer_id))
            self._exec(
                "UPDATE answers SET rating = ? WHERE id = ? AND owner = ?",
                (rating, answer_id, mine),
            )
        feedback_id = uuid.uuid4().hex
        self._exec(
            "INSERT INTO feedback (id, owner, answer_id, database, question, sql, "
            "corrected_sql, rating, comment, provider, model, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                feedback_id,
                mine,
                answer_id,
                database,
                question,
                sql,
                corrected_sql,
                rating,
                comment,
                provider,
                model,
                _now(),
            ),
        )
        return feedback_id

    def examples(self, database: str, owner: str | None = None) -> list[Example]:
        """Verified question/SQL pairs for a database: upvoted answers (their
        corrected SQL when there is one) and downvoted ones the user corrected.
        With an owner, only that owner's feedback."""
        query = (
            "SELECT question, sql, corrected_sql, rating FROM feedback WHERE database = ? "
            "AND (rating = 1 OR corrected_sql IS NOT NULL)"
        )
        params: tuple = (database,)
        if owner is not None:
            query += " AND owner = ?"
            params += (owner_hash(owner),)
        query += " ORDER BY created_at DESC, rowid DESC"
        seen: set[str] = set()
        out = []
        for r in self._exec(query, params):
            key = r["question"].strip().lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(Example(r["question"], r["corrected_sql"] or r["sql"]))
        return out

    def export_feedback(self, database: str | None = None) -> list[dict[str, Any]]:
        """Every feedback row (owner hashes left out), newest first."""
        query = (
            "SELECT id, answer_id, database, question, sql, corrected_sql, rating, comment, "
            "provider, model, created_at FROM feedback"
        )
        params: tuple = ()
        if database:
            query += " WHERE database = ?"
            params = (database,)
        order = " ORDER BY created_at DESC, rowid DESC"
        return [dict(r) for r in self._exec(query + order, params)]
