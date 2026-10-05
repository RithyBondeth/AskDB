"""Turn a public text-to-SQL benchmark into an AskDB eval set.

The Chinook set (dataset.jsonl) is small and written for this project. Spider and
BIRD are the standard benchmarks: many databases, questions written by other
people, so scores on them compare with published results. Download a dev set
(not included here: several hundred MB of SQLite files under their own licenses):

    Spider 1.0 dev   https://yale-lily.github.io/spider (unzip: dev.json, database/)
    BIRD dev         https://bird-bench.github.io (unzip dev.zip, then dev_databases.zip)

then pick a reproducible subset and score a model on it:

    uv run python eval/benchmarks.py spider --source ~/data/spider --limit 200
    uv run python eval/run_eval.py --dataset eval/benchmarks/spider-dev-200.jsonl \\
        --out eval/results/spider-gemini-free.json --delay 5
    uv run python eval/compare.py --dataset spider-dev-200 --readme

The subset is spread evenly across databases (and BIRD difficulty levels), the
same for a given --seed. Questions whose gold SQL doesn't run, or that AskDB's
read-only check would refuse, are left out and counted, since no model could
pass them here. Each row names its SQLite file, so the output works only on the
machine that made it: re-run this command elsewhere instead of copying it.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from askdb.db import QueryError, make_engine, run_query
from askdb.validate import InvalidSQLError, UnsafeQueryError, validate_sql

OUT_DIR = Path(__file__).with_name("benchmarks")
# Gold queries that take longer than this are left out: they'd time out in AskDB too.
GOLD_TIMEOUT_S = 30
_ORDER_BY = re.compile(r"\border\s+by\b", re.I)


def load_spider(source: Path) -> list[dict]:
    """Spider 1.0: dev.json with db_id, question, query; database/<db>/<db>.sqlite."""
    items = json.loads((source / "dev.json").read_text())
    return [
        {
            "db_id": it["db_id"],
            "question": it["question"].strip(),
            "gold_sql": it["query"].strip(),
            "database": str(source / "database" / it["db_id"] / f"{it['db_id']}.sqlite"),
        }
        for it in items
    ]


def load_bird(source: Path) -> list[dict]:
    """BIRD: dev.json with db_id, question, evidence, SQL, difficulty;
    dev_databases/<db>/<db>.sqlite. The evidence (a hint written by the annotators,
    e.g. what a column means) goes with the question, as in BIRD's own setup."""
    items = json.loads((source / "dev.json").read_text())
    out = []
    for it in items:
        question = it["question"].strip()
        if it.get("evidence", "").strip():
            question += f"\nHint: {it['evidence'].strip()}"
        out.append(
            {
                "db_id": it["db_id"],
                "question": question,
                "gold_sql": it["SQL"].strip(),
                "database": str(source / "dev_databases" / it["db_id"] / f"{it['db_id']}.sqlite"),
                "difficulty": it.get("difficulty"),
            }
        )
    return out


LOADERS = {"spider": load_spider, "bird": load_bird}


def spread_sample(items: list[dict], limit: int, seed: int) -> list[dict]:
    """Up to `limit` items, taken round-robin across (database, difficulty) groups
    so no database dominates; within a group the order is shuffled by `seed`."""
    rng = random.Random(seed)
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for it in items:
        groups[(it["db_id"], it.get("difficulty"))].append(it)
    queues = [groups[k] for k in sorted(groups, key=str)]
    for q in queues:
        rng.shuffle(q)
    rng.shuffle(queues)
    picked: list[dict] = []
    while len(picked) < limit and any(queues):
        for q in queues:
            if q and len(picked) < limit:
                picked.append(q.pop())
    return picked


def check_gold(item: dict, engines: dict) -> str | None:
    """Why this question can't be used, or None if it can."""
    path = item["database"]
    if not Path(path).exists():
        return "missing database"
    try:
        validate_sql(item["gold_sql"], "sqlite")
    except (UnsafeQueryError, InvalidSQLError):
        return "gold SQL refused by the read-only check"
    if path not in engines:
        engines[path] = make_engine(f"sqlite:///{path}", GOLD_TIMEOUT_S)
    try:
        run_query(engines[path], item["gold_sql"], 1)
    except QueryError:
        return "gold SQL fails or times out"
    return None


def prepare(
    benchmark: str, source: Path, limit: int, seed: int = 0
) -> tuple[list[dict], Counter[str]]:
    """The eval rows, and how many questions were skipped for each reason."""
    items = LOADERS[benchmark](source)
    engines: dict = {}
    usable, skipped = [], Counter()
    for it in items:
        reason = check_gold(it, engines)
        if reason:
            skipped[reason] += 1
        else:
            usable.append(it)
    for e in engines.values():
        e.dispose()
    rows = []
    for i, it in enumerate(spread_sample(usable, limit, seed)):
        row = {
            "id": f"{benchmark}-{i + 1:04d}-{it['db_id']}",
            "question": it["question"],
            "gold_sql": it["gold_sql"],
            "database": it["database"],
            "db_id": it["db_id"],
            # Order matters only when the gold query asks for one.
            "ordered": bool(_ORDER_BY.search(it["gold_sql"])),
        }
        if it.get("difficulty"):
            row["difficulty"] = it["difficulty"]
        rows.append(row)
    return rows, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("benchmark", choices=sorted(LOADERS))
    parser.add_argument("--source", type=Path, required=True, help="the unzipped dev set")
    parser.add_argument("--limit", type=int, default=200, help="questions to keep (default 200)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    source = args.source.expanduser().resolve()
    if not (source / "dev.json").exists():
        print(f"No dev.json in {source}. Point --source at the unzipped dev set.", file=sys.stderr)
        return 1
    rows, skipped = prepare(args.benchmark, source, args.limit, args.seed)
    out = args.out or OUT_DIR / f"{args.benchmark}-dev-{len(rows)}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    dbs = len({r["db_id"] for r in rows})
    print(f"Wrote {len(rows)} questions from {dbs} databases to {out}")
    for reason, n in skipped.most_common():
        print(f"  skipped {n}: {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
