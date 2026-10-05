"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell as PieCell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { pivot, SERIES, toRecords } from "@/lib/charts";
import { formatAxis, formatCell } from "@/lib/format";
import type { Cell, ChartSpec, ChartType } from "@/lib/types";

export default function ResultChart({
  columns,
  rows,
  chart,
  type,
}: {
  columns: string[];
  rows: Cell[][];
  chart: ChartSpec;
  /** Override the backend's choice (the user's chart-type switch). */
  type?: ChartType;
}) {
  if (chart.type === "none" || !chart.x || !chart.y?.length) return null;
  const kind = type ?? chart.type;
  const x = chart.x;

  // Long-format results become one series per group; otherwise one per y column.
  const grouped = chart.group
    ? pivot(columns, rows, x, chart.group, chart.y[0])
    : { data: toRecords(columns, rows), series: chart.y.slice(0, 3) };
  const { data, series } = grouped;
  const stacked = Boolean(chart.group);

  const labels = data.map((d) => String(d[x] ?? ""));
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
  const tooltipStyle = {
    background: "var(--surface)",
    border: "2px solid var(--ink)",
    borderRadius: "10px 14px 9px 15px / 14px 9px 15px 10px",
    boxShadow: "3px 3px 0 var(--ink)",
    color: "var(--foreground)",
    fontSize: 13,
  };
  const tooltip = {
    contentStyle: tooltipStyle,
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
      dataKey={x}
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
  const margin = { top: 12, right: 16, bottom: 4, left: 0 };

  let body: React.ReactElement;
  if (kind === "pie") {
    const y = chart.y[0];
    const total = data.reduce((sum, d) => sum + (Number(d[y]) || 0), 0);
    body = (
      <PieChart margin={margin}>
        <Tooltip
          {...tooltip}
          formatter={(v: unknown) => {
            const n = Number(v) || 0;
            return `${formatCell(n)} (${total ? Math.round((n / total) * 100) : 0}%)`;
          }}
        />
        <Legend {...legend} />
        <Pie
          data={data.slice(0, SERIES.length)}
          dataKey={y}
          nameKey={x}
          innerRadius="45%"
          outerRadius="80%"
          paddingAngle={1}
          stroke="var(--surface)"
          strokeWidth={2}
          // Direct labels on the big slices only; the legend names the rest.
          label={({ percent }: { percent?: number }) =>
            percent && percent >= 0.06 ? `${Math.round(percent * 100)}%` : ""
          }
          labelLine={false}
          animationDuration={500}
        >
          {data.slice(0, SERIES.length).map((d, i) => (
            <PieCell key={String(d[x])} fill={SERIES[i]} />
          ))}
        </Pie>
      </PieChart>
    );
  } else if (kind === "scatter") {
    const y = chart.y[0];
    const label = chart.label;
    body = (
      <ScatterChart margin={{ ...margin, bottom: 16 }}>
        <CartesianGrid stroke="var(--border)" />
        <XAxis
          type="number"
          dataKey={x}
          name={x}
          {...axis}
          tickFormatter={(v: number) => formatAxis(v)}
          label={{
            value: x,
            position: "insideBottom",
            offset: -8,
            fill: "var(--muted)",
            fontSize: 12,
          }}
        />
        <YAxis
          type="number"
          dataKey={y}
          name={y}
          {...axis}
          axisLine={false}
          width={60}
          tickFormatter={(v: number) => formatAxis(v)}
          label={{
            value: y,
            angle: -90,
            position: "insideLeft",
            fill: "var(--muted)",
            fontSize: 12,
          }}
        />
        <Tooltip
          cursor={{ stroke: "var(--border-strong)", strokeDasharray: "3 3" }}
          content={({ active, payload }) => {
            const point = active && payload?.[0]?.payload;
            if (!point) return null;
            return (
              <div style={{ ...tooltipStyle, padding: "6px 10px" }}>
                {label && <p style={{ fontWeight: 600 }}>{formatCell(point[label])}</p>}
                <p style={{ color: "var(--muted)" }}>
                  {x}: {formatCell(point[x])}
                </p>
                <p style={{ color: "var(--muted)" }}>
                  {y}: {formatCell(point[y])}
                </p>
              </div>
            );
          }}
        />
        <Scatter
          data={data}
          fill={SERIES[0]}
          stroke="var(--surface)"
          strokeWidth={2}
          animationDuration={500}
        />
      </ScatterChart>
    );
  } else if (kind === "line") {
    body = (
      <LineChart data={data} margin={margin}>
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
            connectNulls
            dot={data.length <= 24 ? { r: 4, strokeWidth: 2, fill: "var(--surface)" } : false}
            activeDot={{ r: 5, strokeWidth: 2, stroke: "var(--surface)" }}
            animationDuration={500}
          />
        ))}
      </LineChart>
    );
  } else {
    body = (
      <BarChart data={data} margin={margin} barGap={2}>
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
            stackId={stacked ? "stack" : undefined}
            // Stacked segments get a surface-colored gap; only the top one is rounded.
            stroke={stacked ? "var(--surface)" : undefined}
            strokeWidth={stacked ? 2 : 0}
            radius={!stacked || i === series.length - 1 ? [4, 4, 0, 0] : 0}
            maxBarSize={56}
            animationDuration={500}
          />
        ))}
      </BarChart>
    );
  }

  return (
    <div className="h-80 w-full">
      <ResponsiveContainer width="100%" height="100%">
        {body}
      </ResponsiveContainer>
    </div>
  );
}
