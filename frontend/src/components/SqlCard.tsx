"use client";

export default function SqlCard({ sql, label = "SQL" }: { sql: string; label?: string }) {
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      <div className="flex items-center justify-between border-b border-border px-4 py-2 text-xs text-muted">
        <span>{label}</span>
        <button
          type="button"
          onClick={() => navigator.clipboard?.writeText(sql)}
          className="hover:text-foreground"
        >
          Copy
        </button>
      </div>
      <pre className="whitespace-pre-wrap break-words bg-code px-4 py-3 font-mono text-sm leading-relaxed">
        {sql}
      </pre>
    </div>
  );
}
