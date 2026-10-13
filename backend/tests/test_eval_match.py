import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))

import anthropic  # noqa: E402
import httpx  # noqa: E402
from run_eval import is_config_error, is_unavailable, results_match  # noqa: E402

from askdb.generate import (  # noqa: E402
    GenerationError,
    ProviderConfigError,
    ProviderUnavailableError,
)


def test_unordered_match_ignores_row_and_column_order():
    assert results_match([["b", 2], ["a", 1]], [[1, "a"], [2, "b"]], ordered=False)


def test_ordered_match_respects_order():
    assert not results_match([["b"], ["a"]], [["a"], ["b"]], ordered=True)


def test_extra_columns_tolerated():
    assert results_match([["AC/DC", 22]], [["AC/DC"]], ordered=False)


def test_nulls_and_float_drift():
    assert results_match([[None, 1.0000001]], [[None, 1]], ordered=False)


def test_different_values_fail():
    assert not results_match([["x"]], [["y"]], ordered=False)
    assert not results_match([["x"]], [["x"], ["y"]], ordered=False)


def test_every_gold_query_runs_on_chinook():
    from run_eval import COMPARE_LIMIT, load_dataset

    from askdb.config import BACKEND_DIR
    from askdb.db import make_engine, run_query

    engine = make_engine(f"sqlite:///{BACKEND_DIR / 'data' / 'chinook.sqlite'}", timeout_s=10)
    rows = load_dataset()
    assert len({r["id"] for r in rows}) == len(rows), "duplicate ids"
    for row in rows:
        assert run_query(engine, row["gold_sql"], COMPARE_LIMIT).rows, row["id"]


def test_compare_updates_only_the_readme_table(tmp_path):
    from compare import END, START, update_readme

    readme = tmp_path / "README.md"
    readme.write_text(f"intro\n{START}\nold table\n{END}\noutro\n")
    update_readme(["| new |"], readme)
    assert readme.read_text() == f"intro\n{START}\n| new |\n{END}\noutro\n"


def test_outages_are_told_apart_from_wrong_answers():
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")

    def status(code):
        return anthropic.APIStatusError("x", response=httpx.Response(code, request=req), body=None)

    assert is_unavailable(ProviderUnavailableError("rate limit"))
    assert is_unavailable(status(429)) and is_unavailable(status(529))
    assert is_unavailable(anthropic.APIConnectionError(request=req))
    assert not is_unavailable(status(400))
    assert not is_unavailable(GenerationError("no SQL block"))


def test_setup_problems_are_neither_outages_nor_wrong_answers():
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")

    def status(cls, code):
        return cls("x", response=httpx.Response(code, request=req), body=None)

    assert is_config_error(ProviderConfigError("model not found"))
    assert is_config_error(status(anthropic.NotFoundError, 404))
    assert is_config_error(status(anthropic.AuthenticationError, 401))
    assert not is_config_error(ProviderUnavailableError("503"))
    assert not is_config_error(GenerationError("no SQL block"))
    assert not is_unavailable(ProviderConfigError("model not found"))


def test_eval_stops_on_a_missing_model_without_writing_a_score(monkeypatch, tmp_path, capsys):
    import run_eval

    from askdb.pipeline import AskDB

    calls = []

    def missing_model(self, question, **kw):
        calls.append(question)
        raise ProviderConfigError("Model “gemini-x” not found: no longer available.")

    monkeypatch.setattr(AskDB, "ask", missing_model)
    out = tmp_path / "result.json"
    monkeypatch.setattr(
        sys, "argv", ["run_eval.py", "--provider", "local", "--out", str(out), "--limit", "5"]
    )
    assert run_eval.main() == 2
    assert len(calls) == 1  # stopped at the first question, no retries
    assert not out.exists()  # so the model can't be labelled "0% on eval"
    assert "no results file" in capsys.readouterr().out
