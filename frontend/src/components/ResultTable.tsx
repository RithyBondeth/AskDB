import type { Cell } from "@/lib/types";

function format(v: Cell): string {
  if (v === null) return "NULL";
  if (typeof v === "number" && !Number.isInteger(v))
    return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
  return String(v);
}

export default function ResultTable({
  columns,
  rows,
  truncated,
}: {
  columns: string[];
  rows: Cell[][];
  truncated: boolean;
}) {
  if (rows.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-surface p-4 text-sm text-muted">
        The query ran but returned no rows.
      </div>
    );
  }
  const numeric = columns.map((_, j) =>
    rows.every((r) => r[j] === null || typeof r[j] === "number"),
  );
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      <div className="max-h-[28rem] overflow-auto">
        <table className="w-full text-left text-sm">
          <thead className="sticky top-0 bg-surface">
            <tr className="border-b border-border">
              {columns.map((c, j) => (
                <th
                  key={c}
                  className={`whitespace-nowrap px-4 py-2 font-medium ${numeric[j] ? "text-right" : ""}`}
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-b border-border last:border-0">
                {r.map((v, j) => (
                  <td
                    key={j}
                    className={`whitespace-nowrap px-4 py-2 ${typeof v === "number" ? "text-right tabular-nums" : ""} ${v === null ? "text-muted" : ""}`}
                  >
                    {format(v)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="border-t border-border px-4 py-2 text-xs text-muted">
        {rows.length} {rows.length === 1 ? "row" : "rows"}
        {truncated && ` (first ${rows.length} shown)`}
      </div>
    </div>
  );
}
