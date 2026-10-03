"use client";

import { FileSpreadsheet, FileUp, Loader2, Database, ShieldCheck, X } from "lucide-react";
import { useRef, useState } from "react";

import Doodle from "@/components/Doodle";
import { uploadDatabase } from "@/lib/stream";
import type { AskError, DatabaseInfo } from "@/lib/types";

const ACCEPT = ".db,.sqlite,.sqlite3,.db3,.csv,.tsv,.txt";

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function UploadDialog({
  open,
  onClose,
  onUploaded,
  maxMb,
}: {
  open: boolean;
  onClose: () => void;
  onUploaded: (info: DatabaseInfo) => void;
  maxMb: number;
}) {
  const [files, setFiles] = useState<File[]>([]);
  const [name, setName] = useState("");
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  if (!open) return null;

  const total = files.reduce((n, f) => n + f.size, 0);
  const tooBig = total > maxMb * 1024 * 1024;
  const busy = progress !== null;

  function add(list: FileList | null) {
    if (!list) return;
    setError(null);
    setFiles((prev) => {
      const byName = new Map(prev.map((f) => [f.name, f]));
      Array.from(list).forEach((f) => byName.set(f.name, f));
      return [...byName.values()];
    });
  }

  function close() {
    if (busy) return;
    setFiles([]);
    setName("");
    setError(null);
    onClose();
  }

  async function submit() {
    if (!files.length || tooBig) return;
    setError(null);
    setProgress(0);
    try {
      const info = await uploadDatabase(files, name, setProgress);
      setFiles([]);
      setName("");
      setProgress(null);
      onUploaded(info);
    } catch (e) {
      setProgress(null);
      setError((e as AskError).message);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-[10vh]"
      role="dialog"
      aria-modal="true"
      aria-label="Upload your data"
      onKeyDown={(e) => e.key === "Escape" && close()}
    >
      <button
        type="button"
        aria-label="Close"
        onClick={close}
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
      />
      <div className="card animate-pop-in relative w-full max-w-lg p-5 shadow-2xl">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold">Upload your data</h2>
            <p className="mt-1 text-sm text-muted">
              A SQLite database, or one or more CSV files. Each CSV becomes a table you can join.
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

        <Doodle name="unboxing" className="mx-auto -mb-2 mt-2 w-40" />
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            add(e.dataTransfer.files);
          }}
          disabled={busy}
          className={`mt-2 flex w-full flex-col items-center gap-1.5 rounded-[16px_20px_14px_22px/20px_14px_22px_16px] border-2 border-dashed px-4 py-6 text-center transition ${
            dragging
              ? "border-accent bg-accent-soft"
              : "border-line bg-surface-2 hover:border-ink hover:bg-note-yellow"
          }`}
        >
          <FileUp className="size-6" strokeWidth={2.25} />
          <span className="font-semibold">Drop files here or click to browse</span>
          <span className="text-xs text-subtle">
            .db · .sqlite · .sqlite3 · .csv · .tsv — up to {maxMb} MB
          </span>
        </button>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => {
            add(e.target.files);
            e.target.value = "";
          }}
        />

        {files.length > 0 && (
          <ul className="mt-3 flex flex-col gap-1.5">
            {files.map((f) => {
              const isCsv = /\.(csv|tsv|txt)$/i.test(f.name);
              const Icon = isCsv ? FileSpreadsheet : Database;
              return (
                <li
                  key={f.name}
                  className="flex items-center gap-2.5 rounded-lg bg-surface-2 px-3 py-2 text-sm"
                >
                  <Icon className="size-4 shrink-0 text-muted" />
                  <span className="truncate">{f.name}</span>
                  <span className="ml-auto shrink-0 text-xs text-subtle">{formatSize(f.size)}</span>
                  {!busy && (
                    <button
                      type="button"
                      aria-label={`Remove ${f.name}`}
                      onClick={() => setFiles((fs) => fs.filter((x) => x !== f))}
                      className="grid size-6 place-items-center rounded text-subtle hover:bg-surface hover:text-foreground"
                    >
                      <X className="size-3.5" />
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        )}

        <label className="mt-4 block text-sm">
          <span className="text-muted">Name (optional)</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={80}
            placeholder={files[0]?.name.replace(/\.[^.]+$/, "") ?? "My data"}
            className="sketch-sm mt-1 w-full bg-surface px-3 py-2 outline-none placeholder:text-subtle focus:border-ink"
          />
        </label>

        {(error || tooBig) && (
          <p className="mt-3 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
            {tooBig ? `Files total ${formatSize(total)}, over the ${maxMb} MB limit.` : error}
          </p>
        )}

        {busy && (
          <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-surface-2">
            <div
              className="h-full rounded-full bg-accent transition-[width]"
              style={{ width: `${Math.round((progress ?? 0) * 100)}%` }}
            />
          </div>
        )}

        <div className="mt-5 flex items-center gap-3">
          <p className="flex items-center gap-1.5 text-xs text-subtle">
            <ShieldCheck className="size-3.5" />
            Opened read-only. AskDB never changes your data.
          </p>
          <button
            type="button"
            onClick={submit}
            disabled={!files.length || tooBig || busy}
            className="btn-ink ml-auto inline-flex items-center gap-2 px-4 py-2 text-sm font-medium"
          >
            {busy && <Loader2 className="size-4 animate-spin" />}
            {busy
              ? progress! < 1
                ? `Uploading ${Math.round(progress! * 100)}%`
                : "Preparing…"
              : "Upload"}
          </button>
        </div>
      </div>
    </div>
  );
}
