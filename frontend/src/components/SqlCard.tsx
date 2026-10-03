"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";

import { highlightSql } from "@/lib/sqlHighlight";

export default function SqlCard({
  sql,
  label = "Generated SQL",
  tone = "default",
}: {
  sql: string;
  label?: string;
  tone?: "default" | "failed" | "success";
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard blocked: nothing to do
    }
  }

  const ring =
    tone === "failed"
      ? "border-danger/40"
      : tone === "success"
        ? "border-success/40"
        : "border-border";

  return (
    <div className={`overflow-hidden rounded-xl border ${ring} bg-code`}>
      <div className="flex items-center justify-between border-b border-border px-4 py-2 text-xs text-muted">
        <span className="font-medium">{label}</span>
        <button
          type="button"
          onClick={copy}
          className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 transition hover:bg-surface-2 hover:text-foreground"
        >
          {copied ? <Check className="size-3.5 text-success" /> : <Copy className="size-3.5" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="whitespace-pre-wrap break-words px-4 py-3 font-mono text-[13px] leading-relaxed">
        {highlightSql(sql)}
      </pre>
    </div>
  );
}
