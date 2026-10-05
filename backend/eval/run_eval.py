"""Execution-accuracy harness: does the predicted query return the same rows as the gold query?

    uv run python eval/run_eval.py                       # full dataset, default provider
    uv run python eval/run_eval.py --limit 5             # quick smoke run
    uv run python eval/run_eval.py --provider local      # open model via Ollama
    uv run python eval/run_eval.py --provider claude --model claude-haiku-4-5
    uv run python eval/run_eval.py --out eval/results/claude-v1.json
    uv run python eval/run_eval.py --delay 5             # pace requests (free-tier limits)

With Claude, each question costs an API call (plus repairs). With the local open
model it is free but slower, depending on your hardware.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter
from pathlib import Path
from typing import Any

from askdb.db import QueryError, run_query
from askdb.execute import AnswerError
from askdb.generate import GenerationError
from askdb.pipeline import AskDB
from askdb.providers import PROVIDERS, resolve_model

DATASET = Path(__file__).with_name("dataset.jsonl")
# Gold queries can return more rows than the app shows; compare in full.
COMPARE_LIMIT = 100_000
# A rate-limited question says nothing about accuracy, so wait and ask again
# rather than score it as wrong.
RATE_LIMIT_WAIT_S = 60
RATE_LIMIT_RETRIES = 3


def load_dataset() -> list[dict]:
    return [json.loads(line) for line in DATASET.read_text().splitlines() if line.strip()]


def is_rate_limited(e: Exception) -> bool:
    return isinstance(e, GenerationError) and "rate limit" in str(e).lower()


def _norm(v: Any) -> Any:
    """Make values comparable: round floats, so 1.0 == 1 and SUM drift is ignored."""
    if isinstance(v, float):
        return round(v, 2) if not math.isnan(v) else "NaN"
    if isinstance(v, int) and not isinstance(v, bool):
        return round(float(v), 2)
    return v


def _row_key(row: list[Any]) -> tuple:
    # Compare rows as multisets of values, so column order (and NULLs) don't matter.
    return tuple(sorted((_norm(v) for v in row), key=lambda x: (type(x).__name__, str(x))))


def results_match(pred: list[list], gold: list[list], ordered: bool) -> bool:
    """Execution match.

    Gold columns must all be present; extra predicted columns are tolerated only
    when every gold value still appears in the same row (e.g. the model also
    returned the COUNT it sorted by).
    """
    if len(pred) != len(gold):
        return False
    pred_rows = [_row_key(r) for r in pred]
    gold_rows = [_row_key(r) for r in gold]

    def row_ok(p: tuple, g: tuple) -> bool:
        if p == g:
            return True
        remaining = Counter(p)
        remaining.subtract(Counter(g))
        return all(n >= 0 for n in remaining.values())

    if ordered:
        return all(row_ok(p, g) for p, g in zip(pred_rows, gold_rows, strict=True))
    # Unordered: greedy matching is fine for these small result sets.
    unmatched = list(pred_rows)
    for g in gold_rows:
        hit = next((i for i, p in enumerate(unmatched) if row_ok(p, g)), None)
        if hit is None:
            return False
        unmatched.pop(hit)
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out", type=Path, default=None, help="write per-question results JSON")
    parser.add_argument(
        "--provider",
        choices=PROVIDERS,
        default=None,
        help="override ASKDB_PROVIDER",
    )
    parser.add_argument("--model", default=None, help="a model the provider offers")
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="seconds to wait between questions (free tiers allow a few requests a minute)",
    )
    args = parser.parse_args()

    rows = load_dataset()
    rows = rows[: args.limit] if args.limit else rows
    db = AskDB.from_settings()
    provider = args.provider or db.default_provider
    # Runs on the server's keys, so the ASKDB_*_MODELS allowlists apply.
    model = resolve_model(db.settings, provider, args.model, None)
    print(f"Provider: {provider} ({model})\n")

    results, hits, self_corrected = [], 0, 0
    for i, row in enumerate(rows):
        if i and args.delay:
            time.sleep(args.delay)
        started = time.monotonic()
        gold = run_query(db.engine, row["gold_sql"], COMPARE_LIMIT).rows
        record: dict[str, Any] = {"id": row["id"], "question": row["question"]}
        try:
            for retry in range(RATE_LIMIT_RETRIES + 1):
                try:
                    ans = db.ask(row["question"], provider=provider, model=model)
                    break
                except GenerationError as e:
                    if not is_rate_limited(e) or retry == RATE_LIMIT_RETRIES:
                        raise
                    print(f"      rate limited; waiting {RATE_LIMIT_WAIT_S}s")
                    time.sleep(RATE_LIMIT_WAIT_S)
                    started += RATE_LIMIT_WAIT_S  # don't count the wait as answer time
            pred = run_query(db.engine, ans.sql, COMPARE_LIMIT).rows
            ok = results_match(pred, gold, ordered=row.get("ordered", False))
            record.update(sql=ans.sql, attempts=len(ans.attempts), match=ok)
            self_corrected += ok and len(ans.attempts) > 1
        except (AnswerError, GenerationError, QueryError) as e:
            ok = False
            record.update(sql=None, error=str(e), match=False)
        record["seconds"] = round(time.monotonic() - started, 1)
        hits += ok
        results.append(record)
        print(f"{'PASS' if ok else 'FAIL'}  {row['id']:<24} {record.get('sql') or record['error']}")

    total = len(rows)
    accuracy = hits / total if total else 0.0
    print(f"\nExecution accuracy: {hits}/{total} = {accuracy:.1%}")
    print(f"Passed only after self-correction: {self_corrected}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        summary = {
            "provider": provider,
            "model": model,
            "effort": db.settings.effort if provider == "claude" else None,
            "accuracy": accuracy,
            "hits": hits,
            "total": total,
            "self_corrected": self_corrected,
            "median_seconds": sorted(r["seconds"] for r in results)[total // 2] if total else 0,
            "results": results,
        }
        args.out.write_text(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
