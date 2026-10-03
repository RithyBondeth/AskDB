"""Stage 6: describe the result and pick a chart that fits its shape."""

from __future__ import annotations

import datetime as dt
import decimal
import re
from dataclasses import dataclass
from typing import Any, Literal

ChartType = Literal["bar", "line", "none"]

_DATE_LIKE = re.compile(r"^\d{4}(-\d{2}){0,2}([ T]\d{2}:\d{2}(:\d{2})?)?$")
MAX_BAR_CATEGORIES = 30


@dataclass
class ChartSpec:
    type: ChartType
    x: str | None = None
    y: list[str] | None = None
    reason: str = ""


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


def pick_chart(columns: list[str], rows: list[list[Any]]) -> ChartSpec:
    """Heuristic chart choice.

    - one temporal column + numeric columns  -> line chart over time
    - one label column + numeric columns     -> bar chart (if not too many bars)
    - anything else (single value, wide tables, all text) -> table only
    """
    if len(rows) < 2 or len(columns) < 2:
        return ChartSpec("none", reason="Too few rows or columns to chart.")

    kinds = [_column_kind([r[i] for r in rows]) for i in range(len(columns))]
    numeric = [c for c, k in zip(columns, kinds, strict=True) if k == "number"]
    temporal = [c for c, k in zip(columns, kinds, strict=True) if k == "temporal"]
    category = [c for c, k in zip(columns, kinds, strict=True) if k == "category"]

    if not numeric:
        return ChartSpec("none", reason="No numeric column to plot.")

    if temporal:
        x = temporal[0]
        return ChartSpec("line", x=x, y=numeric[:3], reason=f"Values over {x}.")

    if category:
        if len(rows) > MAX_BAR_CATEGORIES:
            return ChartSpec("none", reason="Too many categories for a bar chart.")
        x = category[0]
        return ChartSpec("bar", x=x, y=numeric[:3], reason=f"Compare values across {x}.")

    # All numeric: treat the first column as the label (e.g. a year or an id).
    if len(numeric) >= 2 and len(rows) <= MAX_BAR_CATEGORIES:
        return ChartSpec("bar", x=numeric[0], y=numeric[1:4], reason=f"Values by {numeric[0]}.")
    return ChartSpec("none", reason="No obvious chart for this shape.")


def to_json_value(v: Any) -> Any:
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, dt.date | dt.datetime | dt.time):
        return v.isoformat()
    if isinstance(v, bytes | bytearray | memoryview):
        return f"<{len(bytes(v))} bytes>"
    return v
