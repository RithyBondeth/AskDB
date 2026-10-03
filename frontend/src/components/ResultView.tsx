"use client";

import { ChartColumn, Clock, Download, Rows3, Sparkles, Table2 } from "lucide-react";
import { useState } from "react";

import AttemptsView from "@/components/AttemptsView";
import PipelineSteps from "@/components/PipelineSteps";
import ResultChart from "@/components/ResultChart";
import ResultTable from "@/components/ResultTable";
import SqlCard from "@/components/SqlCard";
import { downloadText, formatHero, toCsv } from "@/lib/format";
import type { AskResponse } from "@/lib/types";

export default function ResultView({ data, seconds }: { data: AskResponse; seconds: number }) {
  const hasChart = data.chart.type !== "none";
  const [tab, setTab] = useState<"chart" | "table">(hasChart ? "chart" : "table");
  const single = data.rows.length === 1 && data.columns.length === 1;
  const corrected = data.attempts.length > 1;

  return (
    <section className="animate-fade-up flex flex-col gap-4">
      {/* Summary */}
      <div className="card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h2 className="text-lg font-semibold tracking-tight">{data.question}</h2>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
            <Meta icon={Sparkles}>
              <span className="max-w-[14rem] truncate font-mono">{shortModel(data.model)}</span>
            </Meta>
            <Meta icon={Clock}>{seconds.toFixed(1)}s</Meta>
            <Meta icon={Rows3}>
              {data.rows.length}
              {data.truncated ? "+" : ""} {data.rows.length === 1 ? "row" : "rows"}
            </Meta>
          </div>
        </div>
        {data.explanation && (
          <p className="mt-2 text-sm leading-relaxed text-muted">{data.explanation}</p>
        )}
        <div className="mt-4">
          <PipelineSteps data={data} />
        </div>
      </div>

      {/* Answer */}
      {single ? (
        <div className="card relative overflow-hidden p-8 text-center">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(30rem_12rem_at_50%_0%,var(--glow),transparent)]" />
          <p className="relative text-sm text-muted">{data.columns[0]}</p>
          <p className="relative mt-1 text-6xl font-semibold tracking-tight">
            {formatHero(data.rows[0][0])}
          </p>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="flex items-center gap-1 border-b border-border px-2 py-1.5">
            {hasChart && (
              <TabButton
                active={tab === "chart"}
                onClick={() => setTab("chart")}
                icon={ChartColumn}
              >
                Chart
              </TabButton>
            )}
            <TabButton active={tab === "table"} onClick={() => setTab("table")} icon={Table2}>
              Table
            </TabButton>
            <button
              type="button"
              onClick={() => downloadText("askdb-result.csv", toCsv(data.columns, data.rows))}
              className="ml-auto inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs text-muted transition hover:bg-surface-2 hover:text-foreground"
            >
              <Download className="size-3.5" /> CSV
            </button>
          </div>
          {tab === "chart" && hasChart ? (
            <div className="p-4">
              <ResultChart columns={data.columns} rows={data.rows} chart={data.chart} />
              <p className="mt-1 text-xs text-subtle">{data.chart.reason}</p>
            </div>
          ) : (
            <ResultTable columns={data.columns} rows={data.rows} />
          )}
          {data.truncated && (
            <p className="border-t border-border px-4 py-2 text-xs text-muted">
              Showing the first {data.rows.length} rows.
            </p>
          )}
        </div>
      )}

      {/* How it was answered */}
      <div className="card p-5">
        <h3 className="mb-3 text-sm font-medium">
          {corrected ? (
            <>
              Self-corrected after {data.attempts.length - 1} failed{" "}
              {data.attempts.length === 2 ? "attempt" : "attempts"}
            </>
          ) : (
            "How it was answered"
          )}
        </h3>
        {corrected ? <AttemptsView attempts={data.attempts} /> : <SqlCard sql={data.sql} />}
      </div>
    </section>
  );
}

function shortModel(model: string) {
  // "hf.co/mradermacher/Arctic-Text2SQL-R1-7B-GGUF:Q4_K_M" -> "Arctic-Text2SQL-R1-7B-GGUF:Q4_K_M"
  return model.split("/").at(-1) ?? model;
}

function Meta({ icon: Icon, children }: { icon: typeof Clock; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-surface-2 px-2.5 py-1">
      <Icon className="size-3.5" />
      {children}
    </span>
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
  icon: typeof Clock;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition ${
        active ? "bg-surface-2 font-medium text-foreground" : "text-muted hover:text-foreground"
      }`}
    >
      <Icon className="size-4" />
      {children}
    </button>
  );
}
