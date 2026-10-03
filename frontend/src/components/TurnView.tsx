"use client";

import {
  ChevronRight,
  Clock,
  CornerDownRight,
  Link2,
  RotateCcw,
  Rows3,
  Sparkles,
  TriangleAlert,
  User,
} from "lucide-react";
import { useEffect, useState } from "react";

import AttemptsView from "@/components/AttemptsView";
import LivePipeline from "@/components/LivePipeline";
import ResultPanel from "@/components/ResultPanel";
import { FOLLOW_UPS } from "@/lib/examples";
import type { Turn } from "@/lib/types";

export default function TurnView({
  turn,
  isLast,
  busy,
  models,
  onRunSql,
  onRevert,
  onRetry,
  onFollowUp,
  onShare,
}: {
  turn: Turn;
  isLast: boolean;
  busy: boolean;
  models: Record<string, string> | null;
  onRunSql: (sql: string) => Promise<string | null>;
  onRevert: () => void;
  onRetry: () => void;
  onFollowUp: (q: string) => void;
  onShare: () => Promise<void>;
}) {
  const { status, data, error } = turn;
  const elapsed = useElapsed(turn);
  const model = data?.model ?? models?.[turn.provider] ?? turn.provider;
  const corrected = data && data.provider !== "manual" && data.attempts.length > 1;

  return (
    <article
      className={`animate-fade-up flex scroll-mt-20 flex-col gap-3 ${isLast ? "min-h-[calc(100dvh-15rem)]" : ""}`}
    >
      {/* Question */}
      <div className="flex justify-end gap-2.5">
        <p className="max-w-[85%] rounded-2xl rounded-tr-md bg-accent px-4 py-2.5 text-[15px] text-on-accent shadow-sm">
          {turn.question}
        </p>
        <span className="hidden size-8 shrink-0 place-items-center rounded-full bg-surface-2 text-muted sm:grid">
          <User className="size-4" />
        </span>
      </div>

      {/* Answer */}
      <div className="flex gap-2.5">
        <span className="hidden size-8 shrink-0 place-items-center rounded-full bg-gradient-to-br from-[#6d6df0] to-[#3b82f6] text-white shadow-sm sm:grid">
          <Sparkles className="size-4" />
        </span>
        <div className="card min-w-0 flex-1 p-4 sm:p-5">
          <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-muted">
            <span className="max-w-[16rem] truncate font-mono text-foreground">
              {model.split("/").at(-1)}
            </span>
            <Meta icon={Clock}>{elapsed.toFixed(1)}s</Meta>
            {data && (
              <Meta icon={Rows3}>
                {data.rows.length}
                {data.truncated ? "+" : ""} {data.rows.length === 1 ? "row" : "rows"}
              </Meta>
            )}
            <span className="ml-auto flex items-center gap-0.5">
              {status !== "running" && (
                <IconButton label="Ask again" onClick={onRetry} disabled={busy}>
                  <RotateCcw className="size-3.5" />
                </IconButton>
              )}
              <ShareButton onShare={onShare} />
            </span>
          </div>

          <LivePipeline turn={turn} />

          {status === "running" && (
            <div className="mt-4 flex flex-col gap-3" aria-live="polite">
              <div className="skeleton h-4 w-2/3" />
              <div className="flex h-40 items-end gap-2.5">
                {[70, 45, 85, 30, 60, 50, 75, 40].map((h, i) => (
                  <div key={i} className="skeleton flex-1" style={{ height: `${h}%` }} />
                ))}
              </div>
            </div>
          )}

          {status === "done" && data && (
            <div className="mt-4 flex flex-col gap-3">
              {data.explanation && (
                <p className="text-sm leading-relaxed text-muted">{data.explanation}</p>
              )}
              <ResultPanel
                key={data.sql}
                data={data}
                edited={!!turn.original}
                onRunSql={onRunSql}
                onRevert={onRevert}
              />
              {corrected && (
                <details className="group rounded-xl border border-border bg-surface-2/50 px-4 py-3">
                  <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium select-none">
                    <ChevronRight className="size-4 text-muted transition group-open:rotate-90" />
                    Self-corrected after {data.attempts.length - 1} failed{" "}
                    {data.attempts.length === 2 ? "attempt" : "attempts"}
                    <span className="font-normal text-muted">· see what went wrong</span>
                  </summary>
                  <div className="mt-4">
                    <AttemptsView attempts={data.attempts} />
                  </div>
                </details>
              )}
            </div>
          )}

          {status === "error" && error && (
            <div className="mt-4 flex flex-col gap-3">
              <div className="flex items-start gap-3 rounded-xl border border-danger/30 bg-danger-soft p-3.5">
                <TriangleAlert className="mt-0.5 size-4 shrink-0 text-danger" />
                <div className="min-w-0 text-sm">
                  <p className="font-medium text-danger">Couldn’t answer this</p>
                  <p className="mt-0.5 break-words text-muted">{error.message}</p>
                </div>
              </div>
              {error.attempts.length > 0 && (
                <details className="group rounded-xl border border-border px-4 py-3" open>
                  <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium select-none">
                    <ChevronRight className="size-4 text-muted transition group-open:rotate-90" />
                    What was tried
                  </summary>
                  <div className="mt-4">
                    <AttemptsView attempts={error.attempts} />
                  </div>
                </details>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Suggested follow-ups */}
      {isLast && status === "done" && data && data.rows.length > 1 && (
        <div className="flex flex-wrap items-center gap-2 pl-0 sm:pl-[2.6rem]">
          <CornerDownRight className="size-3.5 text-subtle" />
          {FOLLOW_UPS.map((q) => (
            <button
              key={q}
              type="button"
              disabled={busy}
              onClick={() => onFollowUp(q)}
              className="rounded-full border border-border bg-surface px-3 py-1 text-xs text-muted transition hover:border-accent/50 hover:text-foreground disabled:opacity-50"
            >
              {q}
            </button>
          ))}
        </div>
      )}
    </article>
  );
}

function useElapsed(turn: Turn): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (turn.status !== "running") return;
    const id = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(id);
  }, [turn.status]);
  if (turn.seconds !== undefined) return turn.seconds;
  return Math.max(0, (now - turn.startedAt) / 1000);
}

function Meta({ icon: Icon, children }: { icon: typeof Clock; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-surface-2 px-2 py-0.5 tabular-nums">
      <Icon className="size-3" />
      {children}
    </span>
  );
}

function IconButton({
  label,
  onClick,
  disabled,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
      className="grid size-7 place-items-center rounded-md text-muted transition hover:bg-surface-2 hover:text-foreground disabled:opacity-40"
    >
      {children}
    </button>
  );
}

function ShareButton({ onShare }: { onShare: () => Promise<void> }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      title="Copy a link that asks this question"
      onClick={async () => {
        await onShare();
        setDone(true);
        setTimeout(() => setDone(false), 1500);
      }}
      className="inline-flex h-7 items-center gap-1 rounded-md px-2 text-muted transition hover:bg-surface-2 hover:text-foreground"
    >
      <Link2 className="size-3.5" />
      {done ? "Link copied" : "Share"}
    </button>
  );
}
