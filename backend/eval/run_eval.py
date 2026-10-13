"""Execution-accuracy harness: does the predicted query return the same rows as the gold query?

    uv run python eval/run_eval.py                       # full dataset, default provider
    uv run python eval/run_eval.py --limit 5             # quick smoke run
    uv run python eval/run_eval.py --provider local      # open model via Ollama
    uv run python eval/run_eval.py --provider claude --model claude-haiku-4-5
    uv run python eval/run_eval.py --out eval/results/claude-v1.json
    uv run python eval/run_eval.py --delay 5             # pace requests (free-tier limits)
    uv run python eval/run_eval.py --dataset eval/feedback.jsonl  # cases from 👍/👎 feedback
    uv run python eval/run_eval.py --dataset eval/benchmarks/spider-dev-200.jsonl  # benchmarks.py
    uv run python eval/run_eval.py --examples generated  # as an upload: examples from the schema
    uv run python eval/run_eval.py --examples none       # no few-shot examples at all

Rows may name their own SQLite file ("database"), as benchmark rows do; the rest
run against the configured database (ASKDB_DATABASE_URL, Chinook by default).

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

import anthropic

from askdb.db import QueryError, run_query
from askdb.examples import schema_examples
from askdb.execute import AnswerError
from askdb.generate import GenerationError, ProviderConfigError, ProviderUnavailableError
from askdb.pipeline import AskDB
from askdb.providers import PROVIDERS, resolve_model

DATASET = Path(__file__).with_name("dataset.jsonl")
# Gold queries can return more rows than the app shows; compare in full.
COMPARE_LIMIT = 100_000
# A question the provider couldn't answer (rate limit, quota, overload) says
# nothing about accuracy, so wait and ask again rather than score it as wrong.
# If it still can't answer, the question is left out of the accuracy.
UNAVAILABLE_WAIT_S = 60
UNAVAILABLE_RETRIES = 3


def load_dataset(path: Path = DATASET) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def is_unavailable(e: Exception) -> bool:
    """The provider failed to answer at all, as opposed to answering wrongly."""
    if isinstance(e, ProviderUnavailableError):
        return True
    if isinstance(e, anthropic.APIStatusError):
        return e.status_code == 429 or e.status_code >= 500
    return isinstance(e, anthropic.APIConnectionError)  # includes timeouts


def is_config_error(e: Exception) -> bool:
    """No question can succeed until the setup changes: a missing or rejected key,
    or a model the provider doesn't offer this key. Scoring that as wrong answers
    would label the model "0% on eval", so the run stops instead."""
    return isinstance(
        e,
        ProviderConfigError
        | anthropic.AuthenticationError
        | anthropic.PermissionDeniedError
        | anthropic.NotFoundError,
    )


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


def accuracy_by(results: list[dict], key: str) -> dict[str, tuple[int, int]]:
    """{value of `key`: (hits, total)} over the answered results that have it."""
    out: dict[str, tuple[int, int]] = {}
    for r in results:
        if r.get(key) is None or r.get("unavailable"):
            continue
        hits, total = out.get(r[key], (0, 0))
        out[r[key]] = (hits + bool(r["match"]), total + 1)
    return out


def _median(values: list[float]) -> float:
    return sorted(values)[len(values) // 2] if values else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DATASET,
        help="questions and gold SQL, one JSON object per line (default: the Chinook set)",
    )
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
    parser.add_argument(
        "--examples",
        choices=["sample", "generated", "none"],
        default="sample",
        help="few-shot examples: the hand-written ones (default), the ones generated for "
        "uploads, or none. Variant runs never label models in the menu.",
    )
    args = parser.parse_args()

    rows = load_dataset(args.dataset)
    rows = rows[: args.limit] if args.limit else rows
    dataset = "chinook" if args.dataset.resolve() == DATASET.resolve() else args.dataset.stem
    default_db = AskDB.from_settings()
    if args.examples == "generated":
        default_db.examples = schema_examples(default_db.schema, default_db.engine)
    elif args.examples == "none":
        default_db.examples = []
    databases: dict[str, AskDB] = {}

    def database_for(row: dict) -> AskDB:
        """The row's own database (benchmarks), else the configured one."""
        path = row.get("database")
        if not path:
            return default_db
        if path not in databases:
            databases[path] = AskDB.for_database(f"sqlite:///{path}", default_db.settings)
        return databases[path]

    db = default_db
    provider = args.provider or db.default_provider
    # Runs on the server's keys, so the ASKDB_*_MODELS allowlists apply.
    model = resolve_model(db.settings, provider, args.model, None)
    print(
        f"Dataset: {dataset} ({len(rows)} questions)\n"
        f"Provider: {provider} ({model}), examples: {args.examples}\n"
    )

    results, hits, self_corrected, unavailable = [], 0, 0, 0
    for i, row in enumerate(rows):
        if i and args.delay:
            time.sleep(args.delay)
        started = time.monotonic()
        db = database_for(row)
        gold = run_query(db.engine, row["gold_sql"], COMPARE_LIMIT).rows
        record: dict[str, Any] = {"id": row["id"], "question": row["question"]}
        if row.get("difficulty"):
            record["difficulty"] = row["difficulty"]
        try:
            for retry in range(UNAVAILABLE_RETRIES + 1):
                try:
                    ans = db.ask(row["question"], provider=provider, model=model)
                    break
                except Exception as e:
                    if not is_unavailable(e) or retry == UNAVAILABLE_RETRIES:
                        raise
                    print(f"      provider unavailable; waiting {UNAVAILABLE_WAIT_S}s")
                    time.sleep(UNAVAILABLE_WAIT_S)
                    started += UNAVAILABLE_WAIT_S  # don't count the wait as answer time
            pred = run_query(db.engine, ans.sql, COMPARE_LIMIT).rows
            ok = results_match(pred, gold, ordered=row.get("ordered", False))
            record.update(sql=ans.sql, attempts=len(ans.attempts), match=ok)
            self_corrected += ok and len(ans.attempts) > 1
        except Exception as e:
            if is_config_error(e):
                print(f"\nStopped: {e}")
                print(
                    "Nothing was scored and no results file was written. Fix the setup and rerun."
                )
                return 2
            if not (is_unavailable(e) or isinstance(e, AnswerError | GenerationError | QueryError)):
                raise
            ok = False
            record.update(sql=None, error=str(e), match=False)
            if is_unavailable(e):
                record["unavailable"] = True
                unavailable += 1
        record["seconds"] = round(time.monotonic() - started, 1)
        hits += ok
        results.append(record)
        status = "SKIP" if record.get("unavailable") else "PASS" if ok else "FAIL"
        print(f"{status}  {row['id']:<24} {record.get('sql') or record['error']}")

    total = len(rows)
    answered = total - unavailable
    # Accuracy over the questions the provider actually answered.
    accuracy = hits / answered if answered else 0.0
    print(f"\nExecution accuracy: {hits}/{answered} = {accuracy:.1%}")
    print(f"Passed only after self-correction: {self_corrected}")
    if unavailable:
        print(
            f"Not answered (provider unavailable): {unavailable}/{total}. These are left "
            "out of the accuracy; if too few were answered, the run won't label the model "
            "in the menu. Run again later, or with --delay."
        )
    by_difficulty = accuracy_by(results, "difficulty")
    for level, (n_ok, n) in by_difficulty.items():
        print(f"  {level}: {n_ok}/{n} = {n_ok / n:.1%}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        summary = {
            "dataset": dataset,
            "provider": provider,
            "model": model,
            "effort": db.settings.effort if provider == "claude" else None,
            # Set for experiments (e.g. other few-shot examples); None for standard runs.
            "variant": None if args.examples == "sample" else f"examples={args.examples}",
            "accuracy": accuracy,
            "hits": hits,
            "answered": answered,
            "total": total,
            "unavailable": unavailable,
            "self_corrected": self_corrected,
            "by_difficulty": {k: {"hits": h, "total": n} for k, (h, n) in by_difficulty.items()},
            "median_seconds": _median([r["seconds"] for r in results if not r.get("unavailable")]),
            "results": results,
        }
        args.out.write_text(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
