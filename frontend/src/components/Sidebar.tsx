"use client";

import { ChevronRight, Database, History, KeyRound, Plus, Search, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import Doodle from "@/components/Doodle";
import type { SchemaResponse } from "@/lib/types";

export default function Sidebar({
  history,
  onPick,
  onClearHistory,
  onInsert,
  disabled,
  schema,
  schemaFailed,
}: {
  history: string[];
  onPick: (q: string) => void;
  onClearHistory: () => void;
  onInsert: (text: string) => void;
  disabled: boolean;
  schema: SchemaResponse | null;
  schemaFailed: boolean;
}) {
  return (
    <div className="flex w-full flex-col gap-4">
      <HistoryPanel
        history={history}
        onPick={onPick}
        onClear={onClearHistory}
        disabled={disabled}
      />
      <SchemaPanel schema={schema} failed={schemaFailed} onInsert={onInsert} />
    </div>
  );
}

/** The sidebar as a slide-over panel on small screens. */
export function SidebarDrawer({
  open,
  onClose,
  children,
}: {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-40 lg:hidden"
      role="dialog"
      aria-modal="true"
      aria-label="Schema and history"
    >
      <button
        type="button"
        aria-label="Close"
        onClick={onClose}
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
      />
      <div className="animate-slide-in absolute inset-y-0 right-0 flex w-[min(22rem,90vw)] flex-col gap-4 overflow-y-auto border-l border-border bg-background p-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold">Explore</span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="grid size-8 place-items-center rounded-md text-muted hover:bg-surface-2"
          >
            <X className="size-4" />
          </button>
        </div>
        {children}
      </div>
    </div>
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
    <div className="mb-2 flex items-center gap-2 font-hand text-2xl leading-none font-bold">
      <Icon className="size-4.5" strokeWidth={2.25} />
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
        <div className="flex items-center gap-2">
          <Doodle name="laying" className="w-24 shrink-0" />
          <p className="text-xs text-subtle">Questions you ask appear here.</p>
        </div>
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

function SchemaPanel({
  schema,
  failed,
  onInsert,
}: {
  schema: SchemaResponse | null;
  failed: boolean;
  onInsert: (text: string) => void;
}) {
  const [filter, setFilter] = useState("");

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
          <p className="mb-2 text-[11px] text-subtle">
            Click a table or column to add it to your question.
          </p>
          <label className="relative mb-2 block">
            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-subtle" />
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter tables or columns"
              aria-label="Filter tables or columns"
              className="sketch-sm w-full bg-surface py-1.5 pr-2 pl-8 text-sm outline-none placeholder:text-subtle focus:shadow-[2px_2px_0_var(--ink)]"
            />
          </label>
          <ul className="-mx-1 flex max-h-[50vh] flex-col overflow-auto">
            {tables.map((t) => (
              <li key={t.name}>
                <details className="group" open={!!filter.trim()}>
                  <summary className="group/row flex cursor-pointer list-none items-center gap-1.5 rounded-md px-1.5 py-1.5 font-mono text-[13px] transition select-none hover:bg-surface-2">
                    <ChevronRight className="size-3.5 text-subtle transition group-open:rotate-90" />
                    {t.name}
                    <span className="ml-auto font-sans text-[11px] text-subtle group-hover/row:hidden">
                      {t.columns.length}
                    </span>
                    <button
                      type="button"
                      title={`Insert “${t.name}” into your question`}
                      aria-label={`Insert ${t.name} into your question`}
                      onClick={(e) => {
                        e.preventDefault();
                        onInsert(t.name);
                      }}
                      className="ml-auto hidden size-5 place-items-center rounded text-accent-ink hover:bg-accent-soft group-hover/row:grid"
                    >
                      <Plus className="size-3.5" />
                    </button>
                  </summary>
                  <ul className="mt-0.5 mb-1.5 ml-4 border-l border-border pl-3">
                    {t.columns.map((c) => (
                      <li key={c.name}>
                        <button
                          type="button"
                          onClick={() => onInsert(`${t.name}.${c.name}`)}
                          title={`Insert ${t.name}.${c.name} into your question`}
                          className="flex w-full items-center gap-2 rounded px-1 py-0.5 text-left font-mono text-xs transition hover:bg-accent-soft hover:text-accent-ink"
                        >
                          {c.primary_key && (
                            <KeyRound className="size-3 text-accent" aria-label="Primary key" />
                          )}
                          <span>{c.name}</span>
                          <span className="ml-auto text-[11px] text-subtle">
                            {c.type.toLowerCase()}
                          </span>
                        </button>
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
