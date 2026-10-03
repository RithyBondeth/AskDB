"use client";

import { Check, Copy, Loader2, Pencil, Play, RotateCcw, X } from "lucide-react";
import { useState } from "react";

import { highlightSql } from "@/lib/sqlHighlight";

/** Highlighted SQL that can be edited and re-run. Edited SQL goes through the same
 *  read-only validation on the server. */
export default function SqlEditor({
  sql,
  onRun,
  onRevert,
  edited,
}: {
  sql: string;
  onRun?: (sql: string) => Promise<string | null>; // resolves to an error message, or null
  onRevert?: () => void;
  edited?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(sql);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard blocked
    }
  }

  async function run() {
    if (!onRun || !draft.trim()) return;
    setRunning(true);
    setError(null);
    const err = await onRun(draft);
    setRunning(false);
    if (err) setError(err);
    else setEditing(false);
  }

  const btn =
    "inline-flex items-center gap-1.5 rounded-md px-2 py-1 transition hover:bg-surface-2 hover:text-foreground disabled:opacity-50";

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-code">
      <div className="flex items-center gap-1 border-b border-border px-3 py-1.5 text-xs text-muted">
        <span className="mr-auto font-medium">
          {editing ? "Editing SQL" : "SQL"}
          {edited && !editing && (
            <span className="ml-2 rounded-full bg-accent-soft px-2 py-0.5 text-[11px] text-accent-ink">
              edited
            </span>
          )}
        </span>
        {editing ? (
          <>
            <button type="button" className={btn} onClick={() => setEditing(false)}>
              <X className="size-3.5" /> Cancel
            </button>
            <button
              type="button"
              onClick={run}
              disabled={running}
              className="inline-flex items-center gap-1.5 rounded-md bg-accent px-2.5 py-1 font-medium text-on-accent transition hover:bg-accent-hover disabled:opacity-60"
            >
              {running ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Play className="size-3.5" />
              )}
              Run
              <kbd className="hidden font-sans opacity-70 sm:inline">⌘↵</kbd>
            </button>
          </>
        ) : (
          <>
            {edited && onRevert && (
              <button type="button" className={btn} onClick={onRevert}>
                <RotateCcw className="size-3.5" /> Revert
              </button>
            )}
            {onRun && (
              <button
                type="button"
                className={btn}
                onClick={() => {
                  setDraft(sql);
                  setError(null);
                  setEditing(true);
                }}
              >
                <Pencil className="size-3.5" /> Edit
              </button>
            )}
            <button type="button" className={btn} onClick={copy}>
              {copied ? <Check className="size-3.5 text-success" /> : <Copy className="size-3.5" />}
              {copied ? "Copied" : "Copy"}
            </button>
          </>
        )}
      </div>
      {editing ? (
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              run();
            }
          }}
          spellCheck={false}
          autoFocus
          aria-label="SQL"
          rows={Math.min(14, Math.max(4, draft.split("\n").length + 1))}
          className="block w-full resize-y bg-transparent px-4 py-3 font-mono text-[13px] leading-relaxed outline-none"
        />
      ) : (
        <pre className="px-4 py-3 font-mono text-[13px] leading-relaxed break-words whitespace-pre-wrap">
          {highlightSql(sql)}
        </pre>
      )}
      {error && (
        <p className="border-t border-danger/30 bg-danger-soft px-4 py-2 font-mono text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
