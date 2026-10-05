"""Stage 2: schema linking. Pick the tables a question needs, so a database with
hundreds of tables still fits in the prompt.

Each table becomes a small document (its name, column names, comments, and the
tables it references). Tables are ranked by BM25 over those documents and, when
an embedding model is configured, by cosine similarity of embeddings too, with
the two rankings merged by reciprocal rank fusion. The picked tables are then
completed with the tables they reference and with junction tables that connect
two picked tables, so the joins the question needs are possible.
"""

from __future__ import annotations

import logging
import math
import re
import threading
import time
from collections import Counter
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from askdb.schema import Schema, Table

log = logging.getLogger("askdb.linking")

# Small schemas fit in the prompt whole; beyond this, link to relevant tables.
FULL_SCHEMA_MAX_TABLES = 15
TOP_K = 8
# Reciprocal rank fusion constant (the usual choice from the RRF paper).
RRF_K = 60
# After an embedding failure, use BM25 alone for this long before trying again.
EMBED_RETRY_S = 300

_STOPWORDS = {
    "a", "all", "an", "and", "are", "as", "at", "be", "by", "did", "do", "does", "each",
    "for", "from", "give", "has", "have", "how", "i", "in", "is", "it", "list", "many",
    "me", "most", "much", "of", "on", "or", "per", "show", "that", "the", "their", "them",
    "there", "they", "this", "to", "top", "was", "we", "were", "what", "when",
    "where", "which", "who", "whose", "with", "our", "my", "any", "than",
}  # fmt: skip


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


def split_identifier(name: str) -> list[str]:
    """`InvoiceLine`, `invoice_line` -> ["invoice", "line"]."""
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", spaced)
    return [p for p in re.split(r"[^A-Za-z0-9]+", spaced.lower()) if p]


def stem(word: str) -> str:
    """A light stemmer: enough to match "customers" to "customer", "categories" to
    "category", and "sales" to "sale"."""
    if len(word) <= 3:
        return word
    for suffix, repl in (("ies", "y"), ("sses", "ss"), ("xes", "x"), ("ches", "ch")):
        if word.endswith(suffix):
            return word[: -len(suffix)] + repl
    if word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def tokens(text: str) -> list[str]:
    return [stem(t) for t in split_identifier(text) if t not in _STOPWORDS]


def table_document(table: Table) -> str:
    """The text that represents a table for retrieval."""
    parts = [f"Table {table.name}."]
    if table.comment:
        parts.append(table.comment)
    cols = []
    for c in table.columns:
        cols.append(f"{c.name} ({c.comment})" if c.comment else c.name)
    parts.append("Columns: " + ", ".join(cols) + ".")
    refs = sorted({fk.ref_table for fk in table.foreign_keys})
    if refs:
        parts.append("References " + ", ".join(refs) + ".")
    return " ".join(parts)


def _table_terms(table: Table) -> Counter[str]:
    # The table name counts three times: "customers" should find `customer`
    # before it finds every table with a customer_id column.
    terms: Counter[str] = Counter()
    for t in tokens(table.name):
        terms[t] += 3
    for c in table.columns:
        terms.update(tokens(c.name))
        if c.comment:
            terms.update(tokens(c.comment))
    if table.comment:
        terms.update(tokens(table.comment))
    for fk in table.foreign_keys:
        terms.update(tokens(fk.ref_table))
    return terms


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class SchemaIndex:
    """Retrieval over one schema's tables. Build once per database; `link` is
    cheap (BM25) plus one embedding call per question when embeddings are on."""

    def __init__(self, schema: Schema, embedder: Embedder | None = None):
        self.schema = schema
        self.embedder = embedder
        self._docs = [_table_terms(t) for t in schema.tables]
        self._lengths = [sum(d.values()) for d in self._docs]
        self._avg_len = (sum(self._lengths) / len(self._lengths)) if self._lengths else 0.0
        df: Counter[str] = Counter()
        for d in self._docs:
            df.update(d.keys())
        n = len(self._docs)
        self._idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self._table_vectors: list[list[float]] | None = None
        self._embed_failed_at = 0.0
        self._lock = threading.Lock()

    # ------------------------------------------------------------ scoring

    def bm25(self, question: str, k1: float = 1.2, b: float = 0.75) -> list[float]:
        query = set(tokens(question))
        scores = []
        for doc, length in zip(self._docs, self._lengths, strict=True):
            s = 0.0
            for term in query:
                tf = doc.get(term, 0)
                if tf:
                    norm = tf + k1 * (1 - b + b * length / (self._avg_len or 1))
                    s += self._idf[term] * tf * (k1 + 1) / norm
            scores.append(s)
        return scores

    def semantic(self, question: str) -> list[float] | None:
        """Cosine similarity of the question to each table, or None when embeddings
        are off or failing."""
        if self.embedder is None or time.monotonic() - self._embed_failed_at < EMBED_RETRY_S:
            return None
        try:
            with self._lock:
                if self._table_vectors is None:
                    docs = [table_document(t) for t in self.schema.tables]
                    self._table_vectors = self.embedder.embed(docs)
            [q] = self.embedder.embed([question])
        except Exception as e:  # network, quota, bad model name: fall back to BM25
            self._embed_failed_at = time.monotonic()
            log.warning("Embedding failed; using keyword linking for a while: %s", e)
            return None
        return [_cosine(q, v) for v in self._table_vectors]

    # ------------------------------------------------------------ linking

    def link(self, question: str, top_k: int = TOP_K) -> list[Table]:
        tables = self.schema.tables
        if len(tables) <= FULL_SCHEMA_MAX_TABLES:
            return tables

        lexical = self.bm25(question)
        semantic = self.semantic(question)
        if semantic is None:
            ranked = [i for i in sorted(range(len(tables)), key=lambda i: -lexical[i])]
            picked = [i for i in ranked if lexical[i] > 0][:top_k]
        else:
            fused = [0.0] * len(tables)
            for scores in (lexical, semantic):
                order = sorted(range(len(tables)), key=lambda i: -scores[i])
                for rank, i in enumerate(order):
                    if scores[i] > 0:
                        fused[i] += 1 / (RRF_K + rank + 1)
            picked = [i for i in sorted(range(len(tables)), key=lambda i: -fused[i])][:top_k]

        if not picked:
            # Nothing matched: the most connected tables are the best guess.
            picked = sorted(range(len(tables)), key=lambda i: -self._degree(i))[:top_k]
        return self._expand([tables[i] for i in picked], limit=top_k * 2)

    def _degree(self, i: int) -> int:
        name = self.schema.tables[i].name
        inbound = sum(fk.ref_table == name for t in self.schema.tables for fk in t.foreign_keys)
        return inbound + len(self.schema.tables[i].foreign_keys)

    def _expand(self, picked: list[Table], limit: int) -> list[Table]:
        """Add the tables the picked ones reference, and junction tables that link
        two picked tables (e.g. `playlist_track` between `playlist` and `track`)."""
        by_name = {t.name: t for t in self.schema.tables}
        out = list(picked)
        names = {t.name for t in out}
        for t in list(picked):
            for fk in t.foreign_keys:
                ref = by_name.get(fk.ref_table)
                if ref and ref.name not in names and len(out) < limit:
                    out.append(ref)
                    names.add(ref.name)
        picked_names = {t.name for t in picked}
        for t in self.schema.tables:
            if t.name in names or len(out) >= limit:
                continue
            if len({fk.ref_table for fk in t.foreign_keys} & picked_names) >= 2:
                out.append(t)
                names.add(t.name)
        return out


class OpenAIEmbedder:
    """Embeddings from any OpenAI-compatible /embeddings endpoint (Gemini, OpenAI,
    Ollama, vLLM)."""

    def __init__(self, base_url: str, model: str, api_key: str | None, timeout_s: float = 30):
        import httpx

        self.url = base_url.rstrip("/") + "/embeddings"
        self.model = model
        self.api_key = api_key
        self.client = httpx.Client(timeout=timeout_s)

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        for start in range(0, len(texts), 96):  # stay under per-request batch limits
            res = self.client.post(
                self.url,
                headers=headers,
                json={"model": self.model, "input": texts[start : start + 96]},
            )
            res.raise_for_status()
            data = sorted(res.json()["data"], key=lambda d: d["index"])
            out.extend(d["embedding"] for d in data)
        return out
