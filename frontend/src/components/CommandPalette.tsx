"use client";

import { Bot, Cpu, CornerDownLeft, History, Moon, Plus, Search, Sparkles } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { EXAMPLES } from "@/lib/examples";

export interface Command {
  id: string;
  group: "Ask" | "Actions" | "Examples" | "Recent";
  label: string;
  icon: typeof Search;
  hint?: string;
  run: () => void;
}

export function buildCommands({
  history,
  ask,
  newChat,
  setProvider,
  cycleTheme,
}: {
  history: string[];
  ask: (q: string) => void;
  newChat: () => void;
  setProvider: (p: "claude" | "local") => void;
  cycleTheme: () => void;
}): Command[] {
  return [
    { id: "new", group: "Actions", label: "New chat", icon: Plus, run: newChat },
    {
      id: "claude",
      group: "Actions",
      label: "Use Claude",
      icon: Bot,
      run: () => setProvider("claude"),
    },
    {
      id: "local",
      group: "Actions",
      label: "Use the open model",
      icon: Cpu,
      run: () => setProvider("local"),
    },
    {
      id: "theme",
      group: "Actions",
      label: "Change theme",
      icon: Moon,
      hint: "system → light → dark",
      run: cycleTheme,
    },
    ...history.map((q, i) => ({
      id: `h${i}`,
      group: "Recent" as const,
      label: q,
      icon: History,
      run: () => ask(q),
    })),
    ...EXAMPLES.map((e, i) => ({
      id: `e${i}`,
      group: "Examples" as const,
      label: e.text,
      icon: e.icon,
      run: () => ask(e.text),
    })),
  ];
}

export default function CommandPalette({
  open,
  onClose,
  commands,
  onAsk,
}: {
  open: boolean;
  onClose: () => void;
  commands: Command[];
  onAsk: (q: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);
  const listRef = useRef<HTMLUListElement>(null);

  const items = useMemo(() => {
    const q = query.trim().toLowerCase();
    const matched = q ? commands.filter((c) => c.label.toLowerCase().includes(q)) : commands;
    const askItem: Command[] = q
      ? [
          {
            id: "ask",
            group: "Ask",
            label: query.trim(),
            icon: Sparkles,
            hint: "Ask this",
            run: () => onAsk(query.trim()),
          },
        ]
      : [];
    return [...askItem, ...matched];
  }, [query, commands, onAsk]);

  useEffect(() => {
    listRef.current?.querySelector(`[data-index="${index}"]`)?.scrollIntoView({ block: "nearest" });
  }, [index]);

  if (!open) return null;

  function choose(i: number) {
    const item = items[i];
    if (!item) return;
    onClose();
    setQuery("");
    item.run();
  }

  let lastGroup = "";
  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-[12vh]"
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
    >
      <button
        type="button"
        aria-label="Close"
        onClick={onClose}
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
      />
      <div className="card animate-pop-in relative w-full max-w-xl overflow-hidden shadow-2xl">
        <div className="flex items-center gap-3 border-b border-border px-4">
          <Search className="size-4 text-subtle" />
          <input
            autoFocus
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setIndex(0);
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setIndex((i) => Math.min(i + 1, items.length - 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setIndex((i) => Math.max(i - 1, 0));
              } else if (e.key === "Enter") {
                e.preventDefault();
                choose(index);
              } else if (e.key === "Escape") {
                onClose();
              }
            }}
            placeholder="Ask a question or search commands…"
            aria-label="Search commands"
            className="h-12 flex-1 bg-transparent text-[15px] outline-none placeholder:text-subtle"
          />
          <kbd className="rounded border border-border bg-surface-2 px-1.5 text-[11px] text-subtle">
            esc
          </kbd>
        </div>
        <ul ref={listRef} className="max-h-[50vh] overflow-y-auto p-2">
          {items.map((item, i) => {
            const header = item.group !== lastGroup ? item.group : null;
            lastGroup = item.group;
            const Icon = item.icon;
            return (
              <li key={item.id}>
                {header && (
                  <p className="px-2 pt-2 pb-1 text-[11px] font-medium tracking-wide text-subtle uppercase">
                    {header}
                  </p>
                )}
                <button
                  type="button"
                  data-index={i}
                  onMouseMove={() => setIndex(i)}
                  onClick={() => choose(i)}
                  className={`flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left text-sm transition ${
                    i === index ? "bg-accent-soft text-accent-ink" : "text-foreground"
                  }`}
                >
                  <Icon className={`size-4 shrink-0 ${i === index ? "" : "text-muted"}`} />
                  <span className="truncate">{item.label}</span>
                  {item.hint && (
                    <span className="ml-auto shrink-0 text-xs text-subtle">{item.hint}</span>
                  )}
                  {i === index && !item.hint && (
                    <CornerDownLeft className="ml-auto size-3.5 shrink-0" />
                  )}
                </button>
              </li>
            );
          })}
          {items.length === 0 && (
            <li className="px-3 py-6 text-center text-sm text-muted">Type a question to ask it.</li>
          )}
        </ul>
      </div>
    </div>
  );
}
