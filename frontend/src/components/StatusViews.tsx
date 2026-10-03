"use client";

import { Loader2, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";

import AttemptsView from "@/components/AttemptsView";
import type { AskError, Provider } from "@/lib/types";

export function LoadingView({ question, provider }: { question: string; provider: Provider }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const id = setInterval(() => setElapsed((Date.now() - started) / 1000), 100);
    return () => clearInterval(id);
  }, []);

  return (
    <section className="animate-fade-up flex flex-col gap-4" aria-live="polite">
      <div className="card p-5">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold tracking-tight">{question}</h2>
          <span className="font-mono text-xs text-muted tabular-nums">{elapsed.toFixed(1)}s</span>
        </div>
        <p className="mt-2 flex items-center gap-2 text-sm text-muted">
          <Loader2 className="size-4 animate-spin text-accent" />
          {provider === "local"
            ? "The open model is reasoning about your schema. This can take a minute on a laptop."
            : "Writing SQL, checking it is read-only, and running it…"}
        </p>
      </div>
      <div className="card flex flex-col gap-3 p-5">
        <div className="skeleton h-5 w-1/3" />
        <div className="flex h-56 items-end gap-3">
          {[70, 45, 85, 30, 60, 50, 75, 40].map((h, i) => (
            <div key={i} className="skeleton flex-1" style={{ height: `${h}%` }} />
          ))}
        </div>
      </div>
    </section>
  );
}

export function ErrorView({ question, error }: { question: string; error: AskError }) {
  return (
    <section className="animate-fade-up flex flex-col gap-4">
      <div className="card border-danger/40 p-5">
        <div className="flex items-start gap-3">
          <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-danger-soft text-danger">
            <TriangleAlert className="size-4.5" />
          </span>
          <div>
            <h2 className="font-semibold">Couldn’t answer “{question}”</h2>
            <p className="mt-1 text-sm text-muted">{error.message}</p>
          </div>
        </div>
      </div>
      {error.attempts.length > 0 && (
        <div className="card p-5">
          <h3 className="mb-3 text-sm font-medium">What was tried</h3>
          <AttemptsView attempts={error.attempts} />
        </div>
      )}
    </section>
  );
}
