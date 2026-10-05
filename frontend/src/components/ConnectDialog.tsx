"use client";

import { Cable, Loader2, ShieldCheck, X } from "lucide-react";
import { useState } from "react";

import { connectDatabase } from "@/lib/stream";
import type { AskError, DatabaseInfo } from "@/lib/types";

const EXAMPLE = "postgresql://readonly:password@db.example.com:5432/shop";

export default function ConnectDialog({
  open,
  onClose,
  onConnected,
}: {
  open: boolean;
  onClose: () => void;
  onConnected: (info: DatabaseInfo) => void;
}) {
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  function close() {
    if (busy) return;
    setUrl("");
    setName("");
    setError(null);
    onClose();
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const info = await connectDatabase(url.trim(), name);
      setUrl("");
      setName("");
      onConnected(info);
    } catch (err) {
      setError((err as AskError).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-[10vh]"
      role="dialog"
      aria-modal="true"
      aria-label="Connect a database"
      onKeyDown={(e) => e.key === "Escape" && close()}
    >
      <button
        type="button"
        aria-label="Close"
        onClick={close}
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
      />
      <form
        onSubmit={submit}
        className="card animate-pop-in relative w-full max-w-lg p-5 shadow-2xl"
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="font-hand text-4xl leading-none font-bold">Connect a database</h2>
            <p className="mt-1 text-sm text-muted">
              Ask questions of a live PostgreSQL or MySQL database. Only this browser can see it.
            </p>
          </div>
          <button
            type="button"
            onClick={close}
            aria-label="Close"
            className="grid size-8 shrink-0 place-items-center rounded-md text-muted hover:bg-surface-2"
          >
            <X className="size-4" />
          </button>
        </div>

        <label className="mt-4 block text-sm">
          <span className="text-muted">Connection string</span>
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder={EXAMPLE}
            autoComplete="off"
            spellCheck={false}
            required
            className="sketch-sm mt-1 w-full bg-surface px-3 py-2 font-mono text-[13px] outline-none placeholder:text-subtle focus:shadow-[2px_2px_0_var(--ink)]"
          />
        </label>

        <label className="mt-3 block text-sm">
          <span className="text-muted">Name (optional)</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={80}
            placeholder="The database name"
            className="sketch-sm mt-1 w-full bg-surface px-3 py-2 outline-none placeholder:text-subtle focus:shadow-[2px_2px_0_var(--ink)]"
          />
        </label>

        <ul className="mt-4 flex flex-col gap-1.5 rounded-lg bg-surface-2 px-3 py-2.5 text-xs text-muted">
          <li>
            Use a database user that can only <strong>read</strong>. AskDB also opens every
            connection read-only and checks each query before it runs.
          </li>
          <li>
            The connection string is stored on the AskDB server so you can come back to it. It is
            never sent back to the browser. Delete the database here to remove it.
          </li>
        </ul>

        {error && (
          <p className="mt-3 rounded-lg bg-danger-soft px-3 py-2 text-sm break-words text-danger">
            {error}
          </p>
        )}

        <div className="mt-5 flex items-center gap-3">
          <p className="flex items-center gap-1.5 text-xs text-subtle">
            <ShieldCheck className="size-3.5" />
            Read-only, validated SQL.
          </p>
          <button
            type="submit"
            disabled={!url.trim() || busy}
            className="btn-ink ml-auto inline-flex items-center gap-2 px-4 py-2 text-sm font-medium"
          >
            {busy ? <Loader2 className="size-4 animate-spin" /> : <Cable className="size-4" />}
            {busy ? "Connecting…" : "Connect"}
          </button>
        </div>
      </form>
    </div>
  );
}
