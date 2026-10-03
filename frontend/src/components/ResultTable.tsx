"use client";

import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { useMemo, useState } from "react";

import Doodle from "@/components/Doodle";
import { formatCell, isNumericColumn } from "@/lib/format";
import type { Cell } from "@/lib/types";

type Sort = { col: number; dir: "asc" | "desc" } | null;

function compare(a: Cell, b: Cell): number {
  if (a === null) return b === null ? 0 : 1; // NULLs last
  if (b === null) return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), undefined, { numeric: true });
}

export default function ResultTable({
  columns,
  rows,
  filter = "",
}: {
  columns: string[];
  rows: Cell[][];
  filter?: string;
}) {
  const [sort, setSort] = useState<Sort>(null);
  const numeric = columns.map((_, j) => isNumericColumn(rows, j));

  const view = useMemo(() => {
    const f = filter.trim().toLowerCase();
    let out = rows.map((r, i) => ({ r, i }));
    if (f) out = out.filter(({ r }) => r.some((v) => formatCell(v).toLowerCase().includes(f)));
    if (sort) {
      out = [...out].sort(
        (x, y) => compare(x.r[sort.col], y.r[sort.col]) * (sort.dir === "asc" ? 1 : -1),
      );
    }
    return out;
  }, [rows, filter, sort]);

  function toggle(col: number) {
    setSort((s) =>
      s?.col !== col
        ? { col, dir: numeric[col] ? "desc" : "asc" }
        : s.dir === (numeric[col] ? "desc" : "asc")
          ? { col, dir: numeric[col] ? "asc" : "desc" }
          : null,
    );
  }

  if (rows.length === 0) {
    return (
      <div className="flex flex-col items-center gap-1 px-4 py-6 text-center">
        <Doodle name="float" className="w-44" />
        <p className="font-hand text-2xl font-bold">Nothing here</p>
        <p className="text-sm text-muted">The query ran but returned no rows.</p>
      </div>
    );
  }

  return (
    <div>
      <div className="max-h-[28rem] overflow-auto">
        <table className="w-full text-left text-sm">
          <thead className="sticky top-0 z-10 bg-surface/95 backdrop-blur">
            <tr className="border-b border-border">
              <th className="w-10 px-3 py-2.5 text-right text-xs font-medium text-subtle">#</th>
              {columns.map((c, j) => {
                const active = sort?.col === j;
                const Icon = !active ? ArrowUpDown : sort.dir === "asc" ? ArrowUp : ArrowDown;
                return (
                  <th key={c} className={`px-2 py-1.5 ${numeric[j] ? "text-right" : ""}`}>
                    <button
                      type="button"
                      onClick={() => toggle(j)}
                      aria-label={`Sort by ${c}`}
                      className={`group inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium tracking-wide whitespace-nowrap uppercase transition hover:bg-surface-2 ${
                        active ? "text-foreground" : "text-muted"
                      } ${numeric[j] ? "flex-row-reverse" : ""}`}
                    >
                      {c}
                      <Icon
                        className={`size-3 ${active ? "" : "opacity-0 group-hover:opacity-60"}`}
                      />
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {view.map(({ r, i }) => (
              <tr
                key={i}
                className="border-b border-border/70 transition-colors last:border-0 hover:bg-surface-2"
              >
                <td className="px-3 py-2.5 text-right text-xs text-subtle tabular-nums">{i + 1}</td>
                {r.map((v, j) => (
                  <td
                    key={j}
                    className={`px-4 py-2.5 whitespace-nowrap ${numeric[j] ? "text-right tabular-nums" : ""} ${v === null ? "text-subtle italic" : ""}`}
                  >
                    {formatCell(v)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {view.length === 0 && (
          <p className="px-4 py-8 text-center text-sm text-muted">No rows match “{filter}”.</p>
        )}
      </div>
      {filter.trim() && view.length > 0 && (
        <p className="border-t border-border px-4 py-2 text-xs text-muted">
          {view.length} of {rows.length} rows match
        </p>
      )}
    </div>
  );
}
