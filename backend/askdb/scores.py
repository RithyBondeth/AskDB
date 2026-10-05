"""Eval scores for the model menu: how accurate each measured model was.

Reads the result files ``eval/run_eval.py --out`` writes (``eval/results/*.json``).
A model is labelled only from a full run, never from a ``--limit`` smoke run,
and the most accurate measured model of each provider is marked recommended.
With no result files, nothing is labelled.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path

# Smaller runs are smoke tests (--limit), too noisy to label a model with.
MIN_QUESTIONS = 20


@dataclass(frozen=True)
class Score:
    accuracy: float
    hits: int
    total: int
    median_seconds: float | None

    @property
    def label(self) -> str:
        return f"{self.accuracy:.0%} on eval"


_lock = threading.Lock()
_cached: tuple[tuple, dict[tuple[str, str], Score]] | None = None


def load_scores(results_dir: Path) -> dict[tuple[str, str], Score]:
    """{(provider, model): Score}, from the newest full run of each model.

    Re-read only when the files change, so the menu stays cheap to serve."""
    global _cached
    files = sorted(results_dir.glob("*.json")) if results_dir.is_dir() else []
    signature = tuple((f.name, f.stat().st_mtime_ns, f.stat().st_size) for f in files)
    with _lock:
        if _cached and _cached[0] == signature:
            return _cached[1]

    newest: dict[tuple[str, str], tuple[float, Score]] = {}
    for f in files:
        try:
            run = json.loads(f.read_text())
            total = int(run.get("total") or len(run["results"]))
            key = (str(run.get("provider", "claude")), str(run["model"]))
            score = Score(
                accuracy=float(run["accuracy"]),
                hits=int(run.get("hits", round(run["accuracy"] * total))),
                total=total,
                median_seconds=run.get("median_seconds"),
            )
        except (ValueError, KeyError, TypeError):
            continue  # not a results file, or an older format
        if total < MIN_QUESTIONS:
            continue
        mtime = f.stat().st_mtime
        if key not in newest or mtime >= newest[key][0]:
            newest[key] = (mtime, score)

    scores = {k: s for k, (_, s) in newest.items()}
    with _lock:
        _cached = (signature, scores)
    return scores


def annotate(provider: str, models: list[dict], scores: dict[tuple[str, str], Score]) -> None:
    """Add eval results to menu entries in place: ``accuracy``, a ``score`` label,
    and ``recommended`` on the most accurate measured model (fastest on a tie)."""
    measured = [m for m in models if (provider, m["id"]) in scores]
    for m in measured:
        s = scores[(provider, m["id"])]
        m["accuracy"] = s.accuracy
        m["score"] = s.label
    if measured:

        def rank(m: dict) -> tuple[float, float]:
            s = scores[(provider, m["id"])]
            return (s.accuracy, -(s.median_seconds or 0.0))

        max(measured, key=rank)["recommended"] = True
