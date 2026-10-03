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

import type { Cell, ChartSpec } from "@/lib/types";

const SERIES_COLORS = ["var(--accent)", "#d97706", "#0d9488"];

export default function ResultChart({
  columns,
  rows,
  chart,
}: {
  columns: string[];
  rows: Cell[][];
  chart: ChartSpec;
}) {
  if (chart.type === "none" || !chart.x || !chart.y?.length) return null;

  const data = rows.map((r) => Object.fromEntries(columns.map((c, i) => [c, r[i]])));
  const series = chart.y;
  const axisProps = { stroke: "var(--muted)", fontSize: 12, tickLine: false };
  const tooltipStyle = {
    background: "var(--surface)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    color: "var(--foreground)",
  };

  return (
    <figure className="rounded-lg border border-border bg-surface p-4">
      <div className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          {chart.type === "line" ? (
            <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
              <CartesianGrid stroke="var(--border)" vertical={false} />
              <XAxis dataKey={chart.x} {...axisProps} />
              <YAxis {...axisProps} width={56} />
              <Tooltip contentStyle={tooltipStyle} />
              {series.length > 1 && <Legend />}
              {series.map((s, i) => (
                <Line
                  key={s}
                  dataKey={s}
                  stroke={SERIES_COLORS[i % SERIES_COLORS.length]}
                  strokeWidth={2}
                  dot={data.length <= 24}
                />
              ))}
            </LineChart>
          ) : (
            <BarChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
              <CartesianGrid stroke="var(--border)" vertical={false} />
              <XAxis
                dataKey={chart.x}
                {...axisProps}
                interval={0}
                angle={data.length > 5 ? -35 : 0}
                textAnchor={data.length > 5 ? "end" : "middle"}
                height={data.length > 5 ? 70 : 30}
              />
              <YAxis {...axisProps} width={56} />
              <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "var(--accent-soft)" }} />
              {series.length > 1 && <Legend />}
              {series.map((s, i) => (
                <Bar
                  key={s}
                  dataKey={s}
                  fill={SERIES_COLORS[i % SERIES_COLORS.length]}
                  radius={[4, 4, 0, 0]}
                />
              ))}
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-2 text-xs text-muted">{chart.reason}</figcaption>
    </figure>
  );
}
