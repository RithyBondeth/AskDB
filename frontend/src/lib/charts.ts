import type { Cell, ChartSpec, ChartType } from "@/lib/types";

/** Validated categorical slots, in fixed order (never cycled). See globals.css. */
export const SERIES = Array.from({ length: 8 }, (_, i) => `var(--series-${i + 1})`);

/** The chart types worth switching between for a result the backend charted as `spec`. */
export function chartChoices(spec: ChartSpec): ChartType[] {
  switch (spec.type) {
    case "none":
      return [];
    case "scatter":
      return ["scatter"];
    case "pie":
      return ["pie", "bar"];
    default:
      return ["bar", "line"];
  }
}

export type Row = Record<string, Cell>;

/** Rows as objects keyed by column, for Recharts. */
export function toRecords(columns: string[], rows: Cell[][]): Row[] {
  return rows.map((r) => Object.fromEntries(columns.map((c, i) => [c, r[i]])));
}

/**
 * Long format to wide: one record per value of `x`, one key per value of `group`.
 * (country, genre, revenue) -> [{country: "US", Rock: 10, Jazz: 4}, ...]. Groups keep
 * the order they first appear in; past `maxGroups` they fold into "Other".
 */
export function pivot(
  columns: string[],
  rows: Cell[][],
  x: string,
  group: string,
  y: string,
  maxGroups = SERIES.length,
): { data: Row[]; series: string[] } {
  const xi = columns.indexOf(x);
  const gi = columns.indexOf(group);
  const yi = columns.indexOf(y);
  const order: string[] = [];
  for (const r of rows) {
    const g = String(r[gi] ?? "null");
    if (!order.includes(g)) order.push(g);
  }
  const keep = new Set(order.length > maxGroups ? order.slice(0, maxGroups - 1) : order);
  const series = order.length > maxGroups ? [...keep, "Other"] : order;

  const byX = new Map<string, Row>();
  for (const r of rows) {
    const key = String(r[xi] ?? "null");
    const record = byX.get(key) ?? { [x]: r[xi] };
    byX.set(key, record);
    const raw = String(r[gi] ?? "null");
    const g = keep.has(raw) ? raw : "Other";
    const v = typeof r[yi] === "number" ? (r[yi] as number) : 0;
    record[g] = ((record[g] as number | undefined) ?? 0) + v;
  }
  return { data: [...byX.values()], series };
}
