"use client";

import { useEffect, useState } from "react";

import type { SchemaResponse } from "@/lib/types";

export default function SchemaPanel() {
  const [schema, setSchema] = useState<SchemaResponse | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    fetch("/api/schema")
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setSchema)
      .catch(() => setFailed(true));
  }, []);

  return (
    <aside className="w-full shrink-0 lg:w-72">
      <div className="rounded-lg border border-border bg-surface p-4 lg:sticky lg:top-8">
        <h2 className="text-sm font-medium">
          Schema{schema && <span className="text-muted"> · {schema.dialect}</span>}
        </h2>
        {failed && (
          <p className="mt-2 text-sm text-danger">Backend unreachable. Start the API on :8000.</p>
        )}
        {!schema && !failed && <p className="mt-2 text-sm text-muted">Loading…</p>}
        {schema && (
          <ul className="mt-3 flex max-h-[70vh] flex-col gap-1 overflow-auto text-sm">
            {schema.tables.map((t) => (
              <li key={t.name}>
                <details>
                  <summary className="cursor-pointer select-none py-0.5 font-mono">
                    {t.name}
                  </summary>
                  <ul className="mb-2 ml-4 border-l border-border pl-3">
                    {t.columns.map((c) => (
                      <li key={c.name} className="flex justify-between gap-2 font-mono text-xs">
                        <span>{c.name}</span>
                        <span className="text-muted">{c.type.toLowerCase()}</span>
                      </li>
                    ))}
                  </ul>
                </details>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}
