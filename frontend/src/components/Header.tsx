import { Database, PanelRight, Plus, Search, WifiOff } from "lucide-react";
import type { ReactNode } from "react";

import ThemeToggle from "@/components/ThemeToggle";

const iconBtn = "btn-paper grid size-9 place-items-center text-muted hover:text-foreground";

export default function Header({
  offline,
  picker,
  hasThread,
  onNewChat,
  onOpenPalette,
  onOpenSchema,
}: {
  offline: boolean;
  picker: ReactNode;
  hasThread: boolean;
  onNewChat: () => void;
  onOpenPalette: () => void;
  onOpenSchema: () => void;
}) {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-background/90 backdrop-blur-sm">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-2 px-4">
        <button
          type="button"
          onClick={onNewChat}
          className="group flex items-center gap-2"
          title="Home"
        >
          <span className="sketch grid size-8 -rotate-6 place-items-center bg-highlight text-[#1d1b19] transition group-hover:rotate-0">
            <Database className="size-4" strokeWidth={2.25} />
          </span>
          <span className="hidden font-hand text-[26px] leading-none font-bold sm:inline">
            AskDB
          </span>
        </button>
        <span className="hidden text-xl text-border-strong sm:inline">/</span>
        {picker}

        <div className="ml-auto flex items-center gap-2">
          {offline && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-danger-soft px-2.5 py-1 text-xs font-semibold text-danger">
              <WifiOff className="size-3.5" />
              <span className="hidden sm:inline">Backend offline</span>
            </span>
          )}
          {hasThread && (
            <button
              type="button"
              onClick={onNewChat}
              className="btn-paper inline-flex h-9 items-center gap-1.5 px-3 text-sm font-semibold"
            >
              <Plus className="size-4" strokeWidth={2.5} />
              <span className="hidden sm:inline">New chat</span>
            </button>
          )}
          <button
            type="button"
            onClick={onOpenPalette}
            title="Search and commands (⌘K)"
            aria-label="Search and commands"
            className={iconBtn}
          >
            <Search className="size-4" />
          </button>
          <button
            type="button"
            onClick={onOpenSchema}
            aria-label="Show schema"
            className={`${iconBtn} lg:hidden`}
          >
            <PanelRight className="size-4" />
          </button>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
