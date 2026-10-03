"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatAxis, formatCell } from "@/lib/format";
import type { Cell, ChartSpec } from "@/lib/types";

// Validated categorical slots in fixed order (never cycled; the backend caps at 3 series).
const SERIES = ["var(--series-1)", "var(--series-2)", "var(--series-3)"];

export default function ResultChart({
  columns,
  rows,
  chart,
  type,
}: {
  columns: string[];
  rows: Cell[][];
  chart: ChartSpec;
  /** Override the backend's choice (the user's bar/line switch). */
  type?: "bar" | "line";
}) {
  if (chart.type === "none" || !chart.x || !chart.y?.length) return null;
  const kind = type ?? chart.type;

  const data = rows.map((r) => Object.fromEntries(columns.map((c, i) => [c, r[i]])));
  const series = chart.y.slice(0, SERIES.length);
  const labels = data.map((d) => String(d[chart.x!] ?? ""));
  const longest = Math.max(...labels.map((l) => l.length));
  // Rotate when labels would collide; truncate very long ones (full text is in the tooltip).
  const rotate = data.length > 5 || longest * data.length > 40;
  const tickLabel = (v: unknown) => {
    const s = String(v ?? "");
    return s.length > 14 ? `${s.slice(0, 13)}…` : s;
  };
  const axis = {
    stroke: "var(--ink)",
    tick: { fill: "var(--muted)", fontSize: 12, fontFamily: "var(--font-shantell)" },
    tickLine: false,
  };
  const tooltip = {
    contentStyle: {
      background: "var(--surface)",
      border: "2px solid var(--ink)",
      borderRadius: "10px 14px 9px 15px / 14px 9px 15px 10px",
      boxShadow: "3px 3px 0 var(--ink)",
      color: "var(--foreground)",
      fontSize: 13,
    },
    labelStyle: { color: "var(--foreground)", fontWeight: 600, marginBottom: 4 },
    itemStyle: { color: "var(--muted)" },
    formatter: (v: unknown) => formatCell(v as Cell),
  };
  // Legend text stays in the text color; the colored dot carries series identity.
  const legend = {
    iconType: "circle" as const,
    wrapperStyle: { fontSize: 12 },
    formatter: (value: string) => <span style={{ color: "var(--muted)" }}>{value}</span>,
  };
  const xAxis = (
    <XAxis
      dataKey={chart.x}
      {...axis}
      interval={0}
      tickFormatter={tickLabel}
      angle={rotate ? -35 : 0}
      textAnchor={rotate ? "end" : "middle"}
      height={rotate ? 72 : 32}
    />
  );
  const yAxis = (
    <YAxis {...axis} axisLine={false} width={52} tickFormatter={(v: number) => formatAxis(v)} />
  );

  return (
    <div className="h-80 w-full">
      <ResponsiveContainer width="100%" height="100%">
        {kind === "line" ? (
          <LineChart data={data} margin={{ top: 12, right: 16, bottom: 4, left: 0 }}>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            {xAxis}
            {yAxis}
            <Tooltip {...tooltip} cursor={{ stroke: "var(--border-strong)" }} />
            {series.length > 1 && <Legend {...legend} />}
            {series.map((s, i) => (
              <Line
                key={s}
                dataKey={s}
                stroke={SERIES[i]}
                strokeWidth={2}
                dot={data.length <= 24 ? { r: 4, strokeWidth: 2, fill: "var(--surface)" } : false}
                activeDot={{ r: 5, strokeWidth: 2, stroke: "var(--surface)" }}
                animationDuration={500}
              />
            ))}
          </LineChart>
        ) : (
          <BarChart data={data} margin={{ top: 12, right: 16, bottom: 4, left: 0 }} barGap={2}>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            {xAxis}
            {yAxis}
            <Tooltip {...tooltip} cursor={{ fill: "var(--surface-2)" }} />
            {series.length > 1 && <Legend {...legend} />}
            {series.map((s, i) => (
              <Bar
                key={s}
                dataKey={s}
                fill={SERIES[i]}
                radius={[4, 4, 0, 0]}
                maxBarSize={56}
                animationDuration={500}
              />
            ))}
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
