import { CodeXml, Database, PanelRight, Plus, Search } from "lucide-react";

import ThemeToggle from "@/components/ThemeToggle";
import type { HealthResponse } from "@/lib/types";

const iconBtn =
  "grid size-9 place-items-center rounded-lg border border-border bg-surface text-muted transition hover:text-foreground";

export default function Header({
  health,
  offline,
  hasThread,
  onNewChat,
  onOpenPalette,
  onOpenSchema,
}: {
  health: HealthResponse | null;
  offline: boolean;
  hasThread: boolean;
  onNewChat: () => void;
  onOpenPalette: () => void;
  onOpenSchema: () => void;
}) {
  return (
    <header className="sticky top-0 z-30 border-b border-border/70 bg-background/75 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-2 px-4">
        <button
          type="button"
          onClick={onNewChat}
          className="flex items-center gap-2.5"
          title="Home"
        >
          <span className="grid size-8 place-items-center rounded-lg bg-gradient-to-br from-[#6d6df0] to-[#3b82f6] text-white shadow-sm">
            <Database className="size-4" strokeWidth={2.25} />
          </span>
          <span className="text-[15px] font-semibold tracking-tight">AskDB</span>
        </button>

        {hasThread && (
          <button
            type="button"
            onClick={onNewChat}
            className="ml-2 inline-flex h-8 items-center gap-1.5 rounded-lg border border-border bg-surface px-2.5 text-sm text-muted transition hover:text-foreground"
          >
            <Plus className="size-4" />
            <span className="hidden sm:inline">New chat</span>
          </button>
        )}

        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            onClick={onOpenPalette}
            className="hidden h-9 w-60 items-center gap-2 rounded-lg whitespace-nowrap border border-border bg-surface px-3 text-sm text-subtle transition hover:border-border-strong hover:text-muted md:flex"
          >
            <Search className="size-4" />
            Search or ask…
            <kbd className="ml-auto rounded border border-border bg-surface-2 px-1.5 font-sans text-[11px]">
              ⌘K
            </kbd>
          </button>
          <button
            type="button"
            onClick={onOpenPalette}
            aria-label="Command palette"
            className={`${iconBtn} md:hidden`}
          >
            <Search className="size-4" />
          </button>
          <StatusPill health={health} offline={offline} />
          <button
            type="button"
            onClick={onOpenSchema}
            aria-label="Show schema"
            className={`${iconBtn} lg:hidden`}
          >
            <PanelRight className="size-4" />
          </button>
          <a
            href="https://github.com/RithyBondeth/AskDB"
            target="_blank"
            rel="noreferrer"
            title="Source code"
            aria-label="Source code on GitHub"
            className={`${iconBtn} hidden sm:grid`}
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
    <span className="hidden items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-xs text-muted xl:inline-flex">
      <span className={`size-1.5 rounded-full ${dot}`} />
      {label}
    </span>
  );
}
