import { CodeXml, Database } from "lucide-react";

import ThemeToggle from "@/components/ThemeToggle";
import type { HealthResponse } from "@/lib/types";

export default function Header({
  health,
  offline,
}: {
  health: HealthResponse | null;
  offline: boolean;
}) {
  return (
    <header className="sticky top-0 z-20 border-b border-border/70 bg-background/75 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4">
        <div className="flex items-center gap-2.5">
          <div className="grid size-8 place-items-center rounded-lg bg-gradient-to-br from-[#6d6df0] to-[#3b82f6] text-white shadow-sm">
            <Database className="size-4" strokeWidth={2.25} />
          </div>
          <span className="text-[15px] font-semibold tracking-tight">AskDB</span>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <StatusPill health={health} offline={offline} />
          <a
            href="https://github.com/RithyBondeth/AskDB"
            target="_blank"
            rel="noreferrer"
            title="Source code"
            aria-label="Source code on GitHub"
            className="grid size-9 place-items-center rounded-lg border border-border bg-surface text-muted transition hover:text-foreground"
          >
            <CodeXml className="size-4" />
          </a>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

function StatusPill({ health, offline }: { health: HealthResponse | null; offline: boolean }) {
  const [dot, label] = offline
    ? ["bg-danger", "Backend offline"]
    : health
      ? ["bg-success", `${health.dialect} · ${health.tables} tables`]
      : ["bg-subtle animate-pulse", "Connecting…"];
  return (
    <span className="hidden items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-xs text-muted sm:inline-flex">
      <span className={`size-1.5 rounded-full ${dot}`} />
      {label}
    </span>
  );
}
