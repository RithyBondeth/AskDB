"use client";

import { Check, Copy, Laptop, TriangleAlert, X } from "lucide-react";
import { useState } from "react";

import { ownerId, setOwnerId } from "@/lib/owner";

/** Move history and databases between browsers: show this browser's code, or adopt
 *  another browser's. There are no accounts; the code is the key. */
export default function SyncDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [code, setCode] = useState("");
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!open) return null;
  const mine = ownerId();

  function use(e: React.FormEvent) {
    e.preventDefault();
    if (code.trim() === mine) return onClose();
    if (!setOwnerId(code)) {
      setError("That doesn't look like a sync code. Copy it from the other device.");
      return;
    }
    window.location.reload(); // everything on the page belongs to the old id
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-[10vh]"
      role="dialog"
      aria-modal="true"
      aria-label="Use on another device"
      onKeyDown={(e) => e.key === "Escape" && onClose()}
    >
      <button
        type="button"
        aria-label="Close"
        onClick={onClose}
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
      />
      <div className="card animate-pop-in relative w-full max-w-lg p-5 shadow-2xl">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="flex items-center gap-2 font-hand text-4xl leading-none font-bold">
              <Laptop className="size-6" strokeWidth={2.25} />
              Another device
            </h2>
            <p className="mt-1 text-sm text-muted">
              Your history, uploads and connected databases belong to this browser’s sync code.
              Enter it on another device to see them there too.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="grid size-8 shrink-0 place-items-center rounded-md text-muted hover:bg-surface-2"
          >
            <X className="size-4" />
          </button>
        </div>

        <p className="mt-4 text-sm text-muted">This browser’s sync code</p>
        <div className="mt-1 flex items-center gap-2">
          <code className="sketch-sm min-w-0 flex-1 truncate bg-surface-2 px-3 py-2 text-[13px]">
            {mine}
          </code>
          <button
            type="button"
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(mine);
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
              } catch {
                // clipboard blocked: the code is visible to copy by hand
              }
            }}
            className="btn-paper inline-flex items-center gap-1.5 px-3 py-2 text-sm"
          >
            {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
        <p className="mt-2 flex items-start gap-1.5 text-xs text-subtle">
          <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
          Treat it like a password: anyone with this code can see your history and query your
          databases on this server.
        </p>

        <form onSubmit={use} className="mt-5">
          <label className="block text-sm">
            <span className="text-muted">Use a code from another device</span>
            <input
              value={code}
              onChange={(e) => {
                setCode(e.target.value);
                setError(null);
              }}
              placeholder="Paste a sync code"
              autoComplete="off"
              spellCheck={false}
              className="sketch-sm mt-1 w-full bg-surface px-3 py-2 font-mono text-[13px] outline-none placeholder:text-subtle focus:shadow-[2px_2px_0_var(--ink)]"
            />
          </label>
          {error && (
            <p className="mt-2 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
          )}
          <p className="mt-2 text-xs text-subtle">
            This browser then shows the other device’s history and databases instead of its own.
            Keep this browser’s code above if you want to come back to them.
          </p>
          <div className="mt-4 flex justify-end">
            <button
              type="submit"
              disabled={!code.trim()}
              className="btn-ink inline-flex items-center gap-2 px-4 py-2 text-sm font-medium"
            >
              Use this code
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
