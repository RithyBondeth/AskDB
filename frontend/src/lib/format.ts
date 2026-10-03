import type { Cell } from "@/lib/types";

const compact = new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 });
const decimal = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });

export function formatCell(v: Cell): string {
  if (v === null) return "NULL";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : decimal.format(v);
  return String(v);
}

/** Large standalone figures: 1,284 / 12.9K / 4.2M. */
export function formatHero(v: Cell): string {
  if (typeof v !== "number") return formatCell(v);
  return Math.abs(v) >= 10_000 ? compact.format(v) : decimal.format(v);
}

export function formatAxis(v: number): string {
  return Math.abs(v) >= 1000 ? compact.format(v) : decimal.format(v);
}

export function toCsv(columns: string[], rows: Cell[][]): string {
  const esc = (v: Cell) => {
    const s = v === null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [columns.map(esc).join(","), ...rows.map((r) => r.map(esc).join(","))].join("\n");
}

export function downloadText(filename: string, text: string, type = "text/csv") {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function isNumericColumn(rows: Cell[][], j: number): boolean {
  return rows.length > 0 && rows.every((r) => r[j] === null || typeof r[j] === "number");
}
