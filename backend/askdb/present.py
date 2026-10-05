"""Stage 6: describe the result and pick a chart that fits its shape."""

from __future__ import annotations

import datetime as dt
import decimal
import re
from dataclasses import dataclass
from typing import Any, Literal

ChartType = Literal["bar", "line", "pie", "scatter", "none"]

_DATE_LIKE = re.compile(r"^\d{4}(-\d{2}){0,2}([ T]\d{2}:\d{2}(:\d{2})?)?$")
MAX_BAR_CATEGORIES = 30
MAX_PIE_SLICES = 8
MAX_GROUPS = 8  # series in a stacked bar or multi-line chart
# A pie only when the question (or a column) is about parts of a whole.
_SHARE_QUESTION = re.compile(
    r"\b(share|percent(age)?s?|proportions?|breakdown|split|distribution|fractions?|mix)\b|%",
    re.I,
)
_SHARE_COLUMN = re.compile(r"percent|pct|share|ratio|fraction", re.I)


@dataclass
class ChartSpec:
    type: ChartType
    x: str | None = None
    y: list[str] | None = None
    reason: str = ""
    # Long-format results (label, group, value): one series per value of `group`,
    # stacked for bars, one line each for lines.
    group: str | None = None
    # Scatter only: the column that names each point (shown in the tooltip).
    label: str | None = None


def _is_number(v: Any) -> bool:
    return isinstance(v, int | float | decimal.Decimal) and not isinstance(v, bool)


def _is_temporal(v: Any) -> bool:
    return isinstance(v, dt.date | dt.datetime) or (
        isinstance(v, str) and bool(_DATE_LIKE.match(v.strip()))
    )


def _column_kind(values: list[Any]) -> str:
    present = [v for v in values if v is not None]
    if not present:
        return "empty"
    if all(_is_number(v) for v in present):
        return "number"
    if all(_is_temporal(v) for v in present):
        return "temporal"
    return "category"


def _distinct(values: list[Any]) -> int:
    return len({v for v in values})


def _looks_like_label(values: list[Any]) -> bool:
    """Whole numbers, all different, in order: a year or an id, not a measure."""
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in values):
        return False
    if _distinct(values) != len(values):
        return False
    return values == sorted(values) or values == sorted(values, reverse=True)


def pick_chart(columns: list[str], rows: list[list[Any]], question: str = "") -> ChartSpec:
    """Heuristic chart choice.

    - label + group + one number (long format) -> stacked bars, or lines over time
    - one temporal column + numeric columns     -> line chart over time
    - one label + one number, few rows, and the question asks for a share -> pie
    - one label column + numeric columns        -> bar chart (if not too many bars)
    - two or more numbers without a label       -> scatter
    - anything else (single value, all text)    -> table only
    """
    if len(rows) < 2 or len(columns) < 2:
        return ChartSpec("none", reason="Too few rows or columns to chart.")

    col = {c: [r[i] for r in rows] for i, c in enumerate(columns)}
    kinds = {c: _column_kind(v) for c, v in col.items()}
    numeric = [c for c in columns if kinds[c] == "number"]
    temporal = [c for c in columns if kinds[c] == "temporal"]
    category = [c for c in columns if kinds[c] == "category"]

    if not numeric:
        return ChartSpec("none", reason="No numeric column to plot.")

    # Long format, e.g. (country, genre, revenue) or (month, genre, revenue).
    if len(columns) == 3 and len(numeric) == 1 and len(temporal) + len(category) == 2:
        x = temporal[0] if temporal else category[0]
        group = next(c for c in [*temporal, *category] if c != x)
        groups = _distinct(col[group])
        over_time = x in temporal
        if 2 <= groups <= MAX_GROUPS and (over_time or _distinct(col[x]) <= MAX_BAR_CATEGORIES):
            return ChartSpec(
                "line" if over_time else "bar",
                x=x,
                y=numeric,
                group=group,
                reason=f"One {'line' if over_time else 'color'} per {group}: {numeric[0]} by {x}.",
            )

    if temporal:
        x = temporal[0]
        return ChartSpec("line", x=x, y=numeric[:3], reason=f"Values over {x}.")

    if category:
        x = category[0]
        values = col[numeric[0]]
        share = _SHARE_QUESTION.search(question) or _SHARE_COLUMN.search(numeric[0])
        if (
            share
            and len(numeric) == 1
            and len(rows) <= MAX_PIE_SLICES
            and all(v is not None and v >= 0 for v in values)
            and sum(values) > 0
        ):
            return ChartSpec("pie", x=x, y=numeric, reason=f"Share of {numeric[0]} by {x}.")
        if len(rows) <= MAX_BAR_CATEGORIES:
            return ChartSpec("bar", x=x, y=numeric[:3], reason=f"Compare values across {x}.")
        if len(numeric) >= 2:
            return ChartSpec(
                "scatter",
                x=numeric[0],
                y=[numeric[1]],
                label=x,
                reason=f"{numeric[1]} against {numeric[0]}, one point per {x}.",
            )
        return ChartSpec("none", reason="Too many categories for a bar chart.")

    # All numeric. A first column like a year or an id is a label; otherwise
    # two measures are best seen against each other.
    if len(numeric) >= 2:
        if _looks_like_label(col[numeric[0]]) and len(rows) <= MAX_BAR_CATEGORIES:
            return ChartSpec("bar", x=numeric[0], y=numeric[1:4], reason=f"Values by {numeric[0]}.")
        return ChartSpec(
            "scatter",
            x=numeric[0],
            y=[numeric[1]],
            reason=f"{numeric[1]} against {numeric[0]}.",
        )
    return ChartSpec("none", reason="No obvious chart for this shape.")


def _fmt(v: Any) -> str:
    if v is None:
        return "nothing"
    if isinstance(v, bool):
        return str(v).lower()
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, float | decimal.Decimal):
        f = float(v)
        return f"{f:,.0f}" if f.is_integer() else f"{f:,.2f}"
    return str(v)


def _words(column: str) -> str:
    return re.sub(r"([a-z])([A-Z])", r"\1 \2", column).replace("_", " ").strip().lower()


def describe_result(columns: list[str], rows: list[list[Any]], truncated: bool = False) -> str:
    """A plain sentence about a result, without a model: used for the open model
    (which only writes SQL well) and when a model summary fails."""
    if not rows:
        return "No rows matched."
    if len(rows) == 1:
        if len(columns) == 1:
            return f"The answer is {_fmt(rows[0][0])} ({_words(columns[0])})."
        pairs = ", ".join(f"{_words(c)} {_fmt(v)}" for c, v in zip(columns, rows[0], strict=True))
        return f"One row: {pairs}."

    count = f"{len(rows)}{'+' if truncated else ''} rows"
    col = {c: [r[i] for r in rows] for i, c in enumerate(columns)}
    kinds = {c: _column_kind(v) for c, v in col.items()}
    numeric = [c for c in columns if kinds[c] == "number"]
    labels = [c for c in columns if kinds[c] in ("category", "temporal")]
    if not numeric or not labels:
        return f"{count.capitalize()}."

    measure, label = numeric[0], labels[0]
    pairs = [(r_label, v) for r_label, v in zip(col[label], col[measure], strict=True)]
    pairs = [(lbl, v) for lbl, v in pairs if v is not None]
    if not pairs:
        return f"{count.capitalize()}."
    if kinds[label] == "temporal":
        (first_x, first_v), (last_x, last_v) = pairs[0], pairs[-1]
        peak_x, peak_v = max(pairs, key=lambda p: p[1])
        return (
            f"{_words(measure).capitalize()} went from {_fmt(first_v)} ({first_x}) to "
            f"{_fmt(last_v)} ({last_x}), peaking at {_fmt(peak_v)} in {peak_x}."
        )
    top_x, top_v = max(pairs, key=lambda p: p[1])
    low_x, low_v = min(pairs, key=lambda p: p[1])
    return (
        f"{top_x} has the highest {_words(measure)} ({_fmt(top_v)}) and {low_x} the lowest "
        f"({_fmt(low_v)}), across {count}."
    )


def to_json_value(v: Any) -> Any:
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, dt.date | dt.datetime | dt.time):
        return v.isoformat()
    if isinstance(v, bytes | bytearray | memoryview):
        return f"<{len(bytes(v))} bytes>"
    return v
