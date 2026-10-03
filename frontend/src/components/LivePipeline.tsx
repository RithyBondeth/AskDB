import {
  ChartColumn,
  Check,
  Loader2,
  Play,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";

import type { Turn } from "@/lib/types";

const STAGES = [
  { id: "generate", label: "Generate", icon: Sparkles },
  { id: "validate", label: "Validate", icon: ShieldCheck },
  { id: "execute", label: "Execute", icon: Play },
  { id: "present", label: "Present", icon: ChartColumn },
] as const;

type StageId = (typeof STAGES)[number]["id"];
type State = "pending" | "active" | "done" | "failed";

/** The pipeline, live while the question runs and as a summary afterwards. */
export default function LivePipeline({ turn }: { turn: Turn }) {
  const { progress, status, data } = turn;
  const order = STAGES.map((s) => s.id) as StageId[];

  function stateOf(id: StageId): State {
    if (status === "done") return "done";
    const active = (progress.stage ?? "generate") as StageId;
    const i = order.indexOf(id);
    const a = order.indexOf(active);
    if (status === "error") return i < a ? "done" : i === a ? "failed" : "pending";
    return i < a ? "done" : i === a ? "active" : "pending";
  }

  function detailOf(id: StageId): string | null {
    if (status !== "done" || !data) {
      if (id === "generate" && progress.attempt > 1) return `attempt ${progress.attempt}`;
      return null;
    }
    const tries = data.attempts.length;
    if (id === "generate")
      return data.provider === "manual" ? "you" : `${tries} ${tries === 1 ? "draft" : "drafts"}`;
    if (id === "validate") return "read-only";
    if (id === "execute") return `${data.rows.length} ${data.rows.length === 1 ? "row" : "rows"}`;
    return data.rows.length === 1 && data.columns.length === 1
      ? "value"
      : data.chart.type === "none"
        ? "table"
        : data.chart.type;
  }

  const retrying = status === "running" && progress.failures.length > 0;

  return (
    <div className="flex flex-col gap-2">
      <ol className="flex flex-wrap items-center gap-y-2 text-xs">
        {STAGES.map(({ id, label, icon: Icon }, i) => {
          const state = stateOf(id);
          const detail = detailOf(id);
          return (
            <li key={id} className="flex items-center">
              <span
                className={`inline-flex items-center gap-1.5 rounded-[10px_14px_9px_15px/14px_9px_15px_10px] border-[1.5px] px-2.5 py-1 transition-colors duration-300 ${
                  state === "active"
                    ? "border-ink bg-highlight text-[#1d1b19]"
                    : state === "done"
                      ? "border-line bg-surface text-foreground"
                      : state === "failed"
                        ? "border-danger bg-danger-soft text-danger"
                        : "border-dashed border-border-strong text-subtle"
                }`}
              >
                {state === "active" ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : state === "done" ? (
                  <Check className="size-3.5 text-success" strokeWidth={2.5} />
                ) : state === "failed" ? (
                  <X className="size-3.5" strokeWidth={2.5} />
                ) : (
                  <Icon className="size-3.5" />
                )}
                <span className="font-medium">{label}</span>
                {detail && <span className="hidden text-muted sm:inline">· {detail}</span>}
              </span>
              {i < STAGES.length - 1 && (
                <span
                  className={`mx-1 w-4 border-t-2 transition-colors duration-300 ${
                    stateOf(STAGES[i + 1].id) === "pending"
                      ? "border-dashed border-border-strong"
                      : "border-line"
                  }`}
                />
              )}
            </li>
          );
        })}
      </ol>
      {retrying && (
        <p className="flex min-w-0 items-center gap-1.5 text-xs text-accent-ink">
          <RotateCcw className="size-3.5 shrink-0" />
          <span className="shrink-0">
            Attempt {progress.failures.at(-1)!.attempt} failed at {progress.failures.at(-1)!.stage}.
            Self-correcting…
          </span>
          <span className="truncate font-mono text-muted">{progress.failures.at(-1)!.error}</span>
        </p>
      )}
    </div>
  );
}
