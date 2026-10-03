"use client";

import { ChevronRight, Database, History, KeyRound, Search, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type { SchemaResponse } from "@/lib/types";

export default function Sidebar({
  history,
  onPick,
  onClearHistory,
  disabled,
}: {
  history: string[];
  onPick: (q: string) => void;
  onClearHistory: () => void;
  disabled: boolean;
}) {
  return (
    <aside className="flex w-full shrink-0 flex-col gap-4 lg:sticky lg:top-20 lg:w-80 lg:self-start">
      <HistoryPanel
        history={history}
        onPick={onPick}
        onClear={onClearHistory}
        disabled={disabled}
      />
      <SchemaPanel />
    </aside>
  );
}

function PanelTitle({
  icon: Icon,
  children,
  action,
}: {
  icon: typeof History;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-2 flex items-center gap-2 text-sm font-medium">
      <Icon className="size-4 text-muted" />
      {children}
      <span className="ml-auto">{action}</span>
    </div>
  );
}

function HistoryPanel({
  history,
  onPick,
  onClear,
  disabled,
}: {
  history: string[];
  onPick: (q: string) => void;
  onClear: () => void;
  disabled: boolean;
}) {
  return (
    <div className="card p-4">
      <PanelTitle
        icon={History}
        action={
          history.length > 0 && (
            <button
              type="button"
              onClick={onClear}
              aria-label="Clear history"
              className="grid size-7 place-items-center rounded-md text-subtle transition hover:bg-surface-2 hover:text-foreground"
            >
              <Trash2 className="size-3.5" />
            </button>
          )
        }
      >
        Recent
      </PanelTitle>
      {history.length === 0 ? (
        <p className="text-xs text-subtle">Questions you ask appear here.</p>
      ) : (
        <ul className="-mx-1 flex flex-col">
          {history.map((q) => (
            <li key={q}>
              <button
                type="button"
                disabled={disabled}
                onClick={() => onPick(q)}
                className="w-full truncate rounded-md px-2 py-1.5 text-left text-sm text-muted transition hover:bg-surface-2 hover:text-foreground disabled:opacity-50"
                title={q}
              >
                {q}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function SchemaPanel() {
  const [schema, setSchema] = useState<SchemaResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    fetch("/api/schema")
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setSchema)
      .catch(() => setFailed(true));
  }, []);

  const tables = useMemo(() => {
    if (!schema) return [];
    const f = filter.trim().toLowerCase();
    if (!f) return schema.tables;
    return schema.tables.filter(
      (t) =>
        t.name.toLowerCase().includes(f) || t.columns.some((c) => c.name.toLowerCase().includes(f)),
    );
  }, [schema, filter]);

  return (
    <div className="card p-4">
      <PanelTitle
        icon={Database}
        action={
          schema && (
            <span className="rounded-full bg-surface-2 px-2 py-0.5 text-[11px] text-muted">
              {schema.tables.length} tables
            </span>
          )
        }
      >
        Schema
      </PanelTitle>
      {failed && (
        <p className="text-xs text-danger">Backend unreachable. Start the API on port 8000.</p>
      )}
      {!schema && !failed && (
        <div className="flex flex-col gap-2">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-6" />
          ))}
        </div>
      )}
      {schema && (
        <>
          <label className="relative mb-2 block">
            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-subtle" />
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter tables or columns"
              aria-label="Filter tables or columns"
              className="w-full rounded-lg border border-border bg-surface-2 py-1.5 pr-2 pl-8 text-sm outline-none placeholder:text-subtle focus:border-accent/60"
            />
          </label>
          <ul className="-mx-1 flex max-h-[50vh] flex-col overflow-auto">
            {tables.map((t) => (
              <li key={t.name}>
                <details className="group" open={!!filter.trim()}>
                  <summary className="flex cursor-pointer list-none items-center gap-1.5 rounded-md px-1.5 py-1.5 font-mono text-[13px] transition select-none hover:bg-surface-2">
                    <ChevronRight className="size-3.5 text-subtle transition group-open:rotate-90" />
                    {t.name}
                    <span className="ml-auto font-sans text-[11px] text-subtle">
                      {t.columns.length}
                    </span>
                  </summary>
                  <ul className="mt-0.5 mb-1.5 ml-4 border-l border-border pl-3">
                    {t.columns.map((c) => (
                      <li key={c.name} className="flex items-center gap-2 py-0.5 font-mono text-xs">
                        {c.primary_key && (
                          <KeyRound className="size-3 text-accent" aria-label="Primary key" />
                        )}
                        <span>{c.name}</span>
                        <span className="ml-auto text-[11px] text-subtle">
                          {c.type.toLowerCase()}
                        </span>
                      </li>
                    ))}
                  </ul>
                </details>
              </li>
            ))}
            {tables.length === 0 && (
              <li className="px-1.5 py-2 text-xs text-subtle">No match for “{filter}”.</li>
            )}
          </ul>
        </>
      )}
    </div>
  );
}
