"""Turn 👍/👎 feedback from the app into eval cases.

Every answer someone marked correct, and every answer they corrected by editing
the SQL, becomes a question with gold SQL, in the same format as dataset.jsonl:

    uv run python eval/export_feedback.py                         # sample database
    uv run python eval/export_feedback.py --out eval/feedback.jsonl
    uv run python eval/run_eval.py --dataset eval/feedback.jsonl  # then score models on it
    uv run python eval/export_feedback.py --raw                   # every rating, as JSON lines

Review the cases before trusting them: feedback is whatever users clicked. The
eval runs against the configured database (ASKDB_DATABASE_URL), so export the
cases for that database (`--database sample`, the default).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from askdb.config import get_settings
from askdb.store import Store


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--database", default="sample", help="database id (default: sample)")
    parser.add_argument("--out", type=Path, default=None, help="write here instead of stdout")
    parser.add_argument("--raw", action="store_true", help="every rating, not just eval cases")
    args = parser.parse_args()

    settings = get_settings()
    if not Path(settings.store_path).exists():
        print(f"No feedback yet ({settings.store_path} doesn't exist).", file=sys.stderr)
        return 1
    store = Store(settings.store_path)
    if args.raw:
        lines = [json.dumps(r) for r in store.export_feedback(args.database)]
    else:
        lines = [
            json.dumps({"id": f"feedback-{i + 1}", "question": e.question, "gold_sql": e.sql})
            for i, e in enumerate(store.examples(args.database))
        ]
    text = "\n".join(lines) + ("\n" if lines else "")
    if args.out:
        args.out.write_text(text)
        print(f"Wrote {len(lines)} cases to {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
