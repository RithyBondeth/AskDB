import { ChartColumn, Database, Play, RotateCcw, ShieldCheck, Sparkles } from "lucide-react";

import type { AskResponse } from "@/lib/types";

// A summary of what each pipeline stage did for this answer, from the real response.
export default function PipelineSteps({ data }: { data: AskResponse }) {
  const blocked = data.attempts.filter((a) => a.stage === "validate").length;
  const dbErrors = data.attempts.filter((a) => a.stage === "execute").length;
  const retries = data.attempts.length - 1;

  const steps = [
    { icon: Database, label: "Schema", detail: "Read tables" },
    {
      icon: Sparkles,
      label: "Generate",
      detail: retries ? `${data.attempts.length} drafts` : "1 draft",
    },
    {
      icon: ShieldCheck,
      label: "Validate",
      detail: blocked ? `${blocked} rejected` : "Read-only ✓",
    },
    {
      icon: retries ? RotateCcw : Play,
      label: "Execute",
      detail: dbErrors
        ? `${dbErrors} fixed`
        : `${data.rows.length} ${data.rows.length === 1 ? "row" : "rows"}`,
      highlight: retries > 0,
    },
    {
      icon: ChartColumn,
      label: "Present",
      detail:
        data.rows.length === 1 && data.columns.length === 1
          ? "Single value"
          : data.chart.type === "none"
            ? "Table"
            : `${data.chart.type} chart`,
    },
  ];

  return (
    <ol className="flex flex-wrap items-center gap-x-1 gap-y-2 text-xs">
      {steps.map(({ icon: Icon, label, detail, highlight }, i) => (
        <li key={label} className="flex items-center gap-1">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 ${
              highlight
                ? "border-accent/40 bg-accent-soft text-accent-ink"
                : "border-border bg-surface text-muted"
            }`}
          >
            <Icon className="size-3.5" />
            <span className="font-medium text-foreground">{label}</span>
            <span className="hidden sm:inline">· {detail}</span>
          </span>
          {i < steps.length - 1 && <span className="h-px w-3 bg-border-strong" />}
        </li>
      ))}
    </ol>
  );
}
