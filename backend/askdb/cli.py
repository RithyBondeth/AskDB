"""Command-line entry point: `askdb "your question"`."""

from __future__ import annotations

import argparse
import sys

from askdb.execute import AnswerError
from askdb.generate import GenerationError
from askdb.pipeline import AskDB


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ask your database a question in plain English.")
    parser.add_argument("question", nargs="+", help="the question to ask")
    parser.add_argument("--show-schema", action="store_true", help="print the schema DDL first")
    parser.add_argument(
        "--provider", choices=["claude", "local"], default=None, help="override ASKDB_PROVIDER"
    )
    args = parser.parse_args(argv)

    db = AskDB.from_settings()
    if args.show_schema:
        print(db.schema.ddl(), end="\n\n")

    question = " ".join(args.question)
    try:
        ans = db.ask(question, provider=args.provider)
    except AnswerError as e:
        for i, a in enumerate(e.attempts, 1):
            print(f"-- attempt {i} failed ({a.stage}): {a.error}\n{a.sql}\n", file=sys.stderr)
        print(f"error: {e}", file=sys.stderr)
        return 1
    except GenerationError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    for i, a in enumerate(ans.attempts[:-1], 1):
        print(f"-- attempt {i} failed ({a.stage}): {a.error}\n-- self-correcting...\n")
    print(ans.sql, end="\n\n")
    if ans.explanation:
        print(ans.explanation, end="\n\n")
    _print_table(ans.result.columns, ans.result.rows)
    if ans.result.truncated:
        print(f"(showing first {len(ans.result.rows)} rows)")
    return 0


def _print_table(columns: list[str], rows: list[list]) -> None:
    cells = [[("" if v is None else str(v)) for v in r] for r in rows]
    widths = [
        max(len(c), *(len(r[i]) for r in cells)) if cells else len(c) for i, c in enumerate(columns)
    ]
    print("  ".join(c.ljust(w) for c, w in zip(columns, widths, strict=True)))
    print("  ".join("-" * w for w in widths))
    for r in cells:
        print("  ".join(v.ljust(w) for v, w in zip(r, widths, strict=True)))


if __name__ == "__main__":
    raise SystemExit(main())
