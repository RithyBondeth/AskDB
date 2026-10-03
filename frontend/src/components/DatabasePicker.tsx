"use client";

import {
  Check,
  ChevronDown,
  Database,
  FileSpreadsheet,
  Sparkles,
  Trash2,
  Upload,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { DatabaseInfo } from "@/lib/types";

const KIND_ICON = { sample: Sparkles, sqlite: Database, csv: FileSpreadsheet };

export default function DatabasePicker({
  databases,
  current,
  onSelect,
  onUpload,
  onDelete,
  allowUploads,
}: {
  databases: DatabaseInfo[];
  current: DatabaseInfo | undefined;
  onSelect: (id: string) => void;
  onUpload: () => void;
  onDelete: (db: DatabaseInfo) => void;
  allowUploads: boolean;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const Icon = current ? KIND_ICON[current.kind] : Database;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className="btn-paper inline-flex h-9 max-w-[8rem] items-center gap-1.5 px-2 text-sm sm:max-w-[14rem] sm:gap-2 sm:px-2.5"
      >
        <Icon className="size-4 shrink-0 text-accent" />
        <span className="truncate">{current?.name ?? "Loading…"}</span>
        <ChevronDown
          className={`size-3.5 shrink-0 text-subtle transition ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div
          className="card animate-pop-in absolute top-10 left-0 z-40 w-72 p-1.5 shadow-xl"
          role="listbox"
          aria-label="Databases"
        >
          <p className="px-2.5 pt-1.5 pb-1 text-[11px] font-medium tracking-wide text-subtle uppercase">
            Databases
          </p>
          <ul className="max-h-72 overflow-y-auto">
            {databases.map((db) => {
              const KindIcon = KIND_ICON[db.kind];
              const selected = db.id === current?.id;
              return (
                <li key={db.id} className="group flex items-center rounded-lg hover:bg-surface-2">
                  <button
                    type="button"
                    role="option"
                    aria-selected={selected}
                    onClick={() => {
                      onSelect(db.id);
                      setOpen(false);
                    }}
                    className="flex min-w-0 flex-1 items-center gap-2.5 px-2.5 py-2 text-left"
                  >
                    <KindIcon className="size-4 shrink-0 text-muted" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm">{db.name}</span>
                      <span className="block text-[11px] text-subtle">
                        {db.kind === "sample"
                          ? "Sample"
                          : db.kind === "csv"
                            ? "CSV upload"
                            : "SQLite upload"}{" "}
                        · {db.tables} {db.tables === 1 ? "table" : "tables"}
                      </span>
                    </span>
                    {selected && <Check className="size-4 shrink-0 text-accent" />}
                  </button>
                  {db.kind !== "sample" && (
                    <button
                      type="button"
                      onClick={() => onDelete(db)}
                      aria-label={`Delete ${db.name}`}
                      title="Delete"
                      className="mr-1.5 hidden size-7 shrink-0 place-items-center rounded-md text-subtle hover:bg-danger-soft hover:text-danger group-hover:grid"
                    >
                      <Trash2 className="size-3.5" />
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
          {allowUploads && (
            <>
              <div className="my-1 h-px bg-border" />
              <button
                type="button"
                onClick={() => {
                  setOpen(false);
                  onUpload();
                }}
                className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-accent-ink hover:bg-accent-soft"
              >
                <Upload className="size-4" />
                Upload your data…
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
