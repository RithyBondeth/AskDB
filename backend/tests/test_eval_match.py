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
