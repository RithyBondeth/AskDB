import { CodeXml, Database, PanelRight, Plus, Search } from "lucide-react";
import type { ReactNode } from "react";

import ThemeToggle from "@/components/ThemeToggle";

const iconBtn = "btn-paper grid size-8 place-items-center text-foreground sm:size-9";

export default function Header({
  status,
  offline,
  picker,
  hasThread,
  onNewChat,
  onOpenPalette,
  onOpenSchema,
}: {
  status: { dialect: string; tables: number } | null;
  offline: boolean;
  picker: ReactNode;
  hasThread: boolean;
  onNewChat: () => void;
  onOpenPalette: () => void;
  onOpenSchema: () => void;
}) {
  return (
    <header className="sticky top-0 z-30 border-b-2 border-ink bg-background/90 backdrop-blur-sm">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-2 px-4 sm:gap-2.5">
        <button
          type="button"
          onClick={onNewChat}
          className="group flex items-center gap-2"
          title="Home"
        >
          <span className="sketch grid size-8 -rotate-6 place-items-center bg-highlight text-[#1d1b19] transition group-hover:rotate-0">
            <Database className="size-4.5" strokeWidth={2.5} />
          </span>
          <span className="hidden font-hand text-[28px] leading-none font-bold sm:inline">
            AskDB
          </span>
        </button>
        <span className="hidden font-hand text-2xl text-subtle sm:inline">/</span>
        {picker}

        {hasThread && (
          <button
            type="button"
            onClick={onNewChat}
            className="btn-paper inline-flex h-8 items-center gap-1.5 px-2 text-sm font-medium sm:ml-1 sm:h-9 sm:px-3"
          >
            <Plus className="size-4" strokeWidth={2.5} />
            <span className="hidden sm:inline">New chat</span>
          </button>
        )}

        <div className="ml-auto flex items-center gap-2 sm:gap-2.5">
          <button
            type="button"
            onClick={onOpenPalette}
            className="btn-paper hidden h-9 w-60 items-center gap-2 px-3 text-sm whitespace-nowrap text-muted md:flex"
          >
            <Search className="size-4" />
            Search or ask…
            <kbd className="sketch-sm ml-auto bg-surface-2 px-1.5 font-sans text-[11px] text-foreground">
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
          <StatusPill status={status} offline={offline} />
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

function StatusPill({
  status,
  offline,
}: {
  status: { dialect: string; tables: number } | null;
  offline: boolean;
}) {
  const [dot, label] = offline
    ? ["bg-danger", "Backend offline"]
    : status
      ? ["bg-success", `${status.dialect} · ${status.tables} tables`]
      : ["bg-subtle animate-pulse", "Connecting…"];
  return (
    <span className="sketch-sm hidden items-center gap-2 bg-surface px-3 py-1 text-xs text-muted xl:inline-flex">
      <span className={`size-2 rounded-full border border-ink ${dot}`} />
      {label}
    </span>
  );
}
