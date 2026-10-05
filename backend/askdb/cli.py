"""Command-line entry point: `askdb "your question"`."""

from __future__ import annotations

import argparse
import sys

import httpx

from askdb.config import get_settings
from askdb.execute import AnswerError
from askdb.generate import GenerationError
from askdb.hosted import error_detail
from askdb.pipeline import AskDB
from askdb.providers import (
    HOSTED,
    PROVIDERS,
    ModelNotAllowed,
    fetch_hosted_models,
    hosted_config,
    resolve_model,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ask your database a question in plain English.")
    parser.add_argument("question", nargs="*", help="the question to ask")
    parser.add_argument("--show-schema", action="store_true", help="print the schema DDL first")
    parser.add_argument(
        "--provider",
        choices=PROVIDERS,
        default=None,
        help="override ASKDB_PROVIDER",
    )
    parser.add_argument("--model", default=None, help="a model the provider offers")
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="list the models a hosted provider (default: free) offers your key, then exit",
    )
    args = parser.parse_args(argv)

    if args.list_models:
        return _list_models(args.provider if args.provider in HOSTED else "free")
    if not args.question:
        parser.error('ask a question, e.g. askdb "Which artist has the most albums?"')

    db = AskDB.from_settings()
    if args.show_schema:
        print(db.schema.ddl(), end="\n\n")

    question = " ".join(args.question)
    provider = args.provider or db.default_provider
    try:
        # The CLI runs with the server's own keys, so the operator's allowlists apply.
        model = resolve_model(db.settings, provider, args.model, None)
    except ModelNotAllowed as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    try:
        ans = db.ask(question, provider=provider, model=model)
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


def _list_models(provider: str) -> int:
    cfg = hosted_config(get_settings(), provider)
    try:
        models = fetch_hosted_models(cfg.base_url, cfg.api_key)
    except httpx.HTTPStatusError as e:
        print(f"error: {e.response.status_code}: {error_detail(e.response)}", file=sys.stderr)
        return 1
    except httpx.HTTPError as e:
        print(f"error: couldn't reach {cfg.base_url}: {e}", file=sys.stderr)
        return 1
    env = f"ASKDB_{provider.upper()}_MODEL"
    print(f"Models at {cfg.base_url} (current {env}: {cfg.default}):")
    for m in models:
        print(f"  {m}")
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
