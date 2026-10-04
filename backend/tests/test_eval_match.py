import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))

from run_eval import results_match  # noqa: E402


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
