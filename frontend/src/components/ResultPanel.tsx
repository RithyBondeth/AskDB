"use client";

import {
  ChartColumn,
  ChartLine,
  ChartPie,
  ChartScatter,
  Code2,
  Download,
  Loader2,
  Search,
  Table2,
} from "lucide-react";
import { useState } from "react";

import ResultChart from "@/components/ResultChart";
import ResultTable from "@/components/ResultTable";
import SqlEditor from "@/components/SqlEditor";
import { chartChoices } from "@/lib/charts";
import { downloadText, formatHero, toCsv } from "@/lib/format";
import type { AskResponse, ChartType } from "@/lib/types";

type Tab = "chart" | "table" | "sql";

const CHART_ICONS = { bar: ChartColumn, line: ChartLine, pie: ChartPie, scatter: ChartScatter };

export default function ResultPanel({
  data,
  edited,
  onRunSql,
  onRevert,
  onMoreRows,
  onExportAll,
}: {
  data: AskResponse;
  edited: boolean;
  onRunSql: (sql: string) => Promise<string | null>;
  onRevert: () => void;
  /** Fetch the next page of rows into this answer; resolves with an error message or null. */
  onMoreRows?: () => Promise<string | null>;
  /** Download every row as CSV, not just the ones loaded. */
  onExportAll?: () => Promise<string | null>;
}) {
  const hasChart = data.chart.type !== "none";
  const single = data.rows.length === 1 && data.columns.length === 1;
  const [tab, setTab] = useState<Tab>(hasChart ? "chart" : "table");
  const [chartType, setChartType] = useState<ChartType | undefined>(undefined);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState<"rows" | "export" | null>(null);
  const [rowsError, setRowsError] = useState<string | null>(null);
  const activeTab: Tab = tab === "chart" && !hasChart ? "table" : tab;
  const choices = chartChoices(data.chart);

  async function busyWith(what: "rows" | "export", fn?: () => Promise<string | null>) {
    if (!fn || loading) return;
    setLoading(what);
    setRowsError(await fn());
    setLoading(null);
  }

  return (
    <div className="sketch overflow-hidden">
      <div className="flex flex-wrap items-center gap-1 border-b-2 border-ink bg-surface-2 px-1.5 py-1.5">
        {hasChart && !single && (
          <TabButton
            active={activeTab === "chart"}
            onClick={() => setTab("chart")}
            icon={ChartColumn}
          >
            Chart
          </TabButton>
        )}
        <TabButton active={activeTab === "table"} onClick={() => setTab("table")} icon={Table2}>
          {single ? "Answer" : "Table"}
        </TabButton>
        <TabButton active={activeTab === "sql"} onClick={() => setTab("sql")} icon={Code2}>
          SQL
        </TabButton>

        <div className="ml-auto flex items-center gap-1">
          {activeTab === "chart" && choices.length > 1 && (
            <div
              className="sketch-sm inline-flex bg-surface p-0.5"
              role="group"
              aria-label="Chart type"
            >
              {choices.map((t) => {
                const Icon = CHART_ICONS[t];
                const on = (chartType ?? data.chart.type) === t;
                return (
                  <button
                    key={t}
                    type="button"
                    aria-pressed={on}
                    title={`${t} chart`}
                    onClick={() => setChartType(t)}
                    className={`grid size-7 place-items-center rounded-md transition ${on ? "bg-highlight text-[#1d1b19]" : "text-muted hover:text-foreground"}`}
                  >
                    <Icon className="size-3.5" />
                  </button>
                );
              })}
            </div>
          )}
          {activeTab === "table" && !single && (
            <label className="relative">
              <Search className="pointer-events-none absolute top-1/2 left-2 size-3.5 -translate-y-1/2 text-subtle" />
              <input
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="Filter rows"
                aria-label="Filter rows"
                className="sketch-sm w-32 bg-surface py-1 pr-2 pl-7 text-xs outline-none placeholder:text-subtle focus:shadow-[2px_2px_0_var(--ink)] sm:w-40"
              />
            </label>
          )}
          {activeTab !== "sql" && (
            <button
              type="button"
              title={
                data.truncated && onExportAll
                  ? "Download every row as CSV, not just the ones shown"
                  : "Download these rows as CSV"
              }
              disabled={loading === "export"}
              onClick={() =>
                data.truncated && onExportAll
                  ? busyWith("export", onExportAll)
                  : downloadText("askdb-result.csv", toCsv(data.columns, data.rows))
              }
              className="inline-flex items-center gap-1.5 rounded-md px-2 py-1.5 text-xs text-muted transition hover:bg-surface-2 hover:text-foreground disabled:opacity-60"
            >
              {loading === "export" ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Download className="size-3.5" />
              )}
              {data.truncated && onExportAll ? "All rows CSV" : "CSV"}
            </button>
          )}
        </div>
      </div>

      <div className="bg-surface">
        {activeTab === "chart" && hasChart && !single && (
          <div className="animate-fade-up p-4">
            <ResultChart
              columns={data.columns}
              rows={data.rows}
              chart={data.chart}
              type={chartType}
            />
            <p className="mt-1 text-xs text-subtle">{data.chart.reason}</p>
          </div>
        )}
        {activeTab === "table" &&
          (single ? (
            <div className="relative overflow-hidden px-6 py-10 text-center">
              <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(30rem_12rem_at_50%_0%,var(--glow),transparent)]" />
              <p className="relative text-sm text-muted">{data.columns[0]}</p>
              <p className="relative mt-1 text-6xl font-semibold tracking-tight">
                {formatHero(data.rows[0][0])}
              </p>
            </div>
          ) : (
            <ResultTable columns={data.columns} rows={data.rows} filter={filter} />
          ))}
        {activeTab === "sql" && (
          <div className="p-3">
            <SqlEditor sql={data.sql} edited={edited} onRun={onRunSql} onRevert={onRevert} />
          </div>
        )}
        {data.truncated && activeTab !== "sql" && (
          <div className="flex flex-wrap items-center gap-3 border-t border-border px-4 py-2 text-xs text-muted">
            <span>Showing the first {data.rows.length} rows.</span>
            {onMoreRows && (
              <button
                type="button"
                onClick={() => busyWith("rows", onMoreRows)}
                disabled={loading === "rows"}
                className="btn-paper inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium disabled:opacity-60"
              >
                {loading === "rows" && <Loader2 className="size-3.5 animate-spin" />}
                Load more
              </button>
            )}
            {rowsError && <span className="text-danger">{rowsError}</span>}
          </div>
        )}
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  icon: Icon,
  children,
}: {
  active: boolean;
  onClick: () => void;
  icon: typeof Code2;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`inline-flex items-center gap-1.5 rounded-[9px_12px_8px_13px/12px_8px_13px_9px] border-[1.5px] px-3 py-1 text-sm transition ${
        active
          ? "border-ink bg-surface font-medium text-foreground shadow-[2px_2px_0_var(--ink)]"
          : "border-transparent text-muted hover:text-foreground"
      }`}
    >
      <Icon className="size-4" />
      {children}
    </button>
  );
}
