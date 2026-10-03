import { formatCell, isNumericColumn } from "@/lib/format";
import type { Cell } from "@/lib/types";

export default function ResultTable({ columns, rows }: { columns: string[]; rows: Cell[][] }) {
  if (rows.length === 0) {
    return (
      <p className="px-4 py-10 text-center text-sm text-muted">
        The query ran but returned no rows.
      </p>
    );
  }
  const numeric = columns.map((_, j) => isNumericColumn(rows, j));
  return (
    <div className="max-h-[28rem] overflow-auto">
      <table className="w-full text-left text-sm">
        <thead className="sticky top-0 z-10 bg-surface">
          <tr className="border-b border-border">
            <th className="w-10 px-3 py-2.5 text-right text-xs font-medium text-subtle">#</th>
            {columns.map((c, j) => (
              <th
                key={c}
                className={`whitespace-nowrap px-4 py-2.5 text-xs font-medium tracking-wide text-muted uppercase ${numeric[j] ? "text-right" : ""}`}
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr
              key={i}
              className="border-b border-border/70 transition-colors last:border-0 hover:bg-surface-2"
            >
              <td className="px-3 py-2.5 text-right text-xs text-subtle tabular-nums">{i + 1}</td>
              {r.map((v, j) => (
                <td
                  key={j}
                  className={`whitespace-nowrap px-4 py-2.5 ${numeric[j] ? "text-right tabular-nums" : ""} ${v === null ? "text-subtle italic" : ""}`}
                >
                  {formatCell(v)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
