"use client";

import { ArrowUp, Bot, Cpu } from "lucide-react";
import { useEffect, useRef } from "react";

import type { Provider } from "@/lib/types";

const PROVIDERS: { id: Provider; label: string; icon: typeof Bot }[] = [
  { id: "claude", label: "Claude", icon: Bot },
  { id: "local", label: "Open model", icon: Cpu },
];

export default function Composer({
  value,
  onChange,
  onSubmit,
  provider,
  onProviderChange,
  models,
  busy,
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  provider: Provider;
  onProviderChange: (p: Provider) => void;
  models: Record<Provider, string> | null;
  busy: boolean;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);

  // Grow with content, up to a few lines.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [value]);

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
      className="card group p-2 transition focus-within:border-accent/60 focus-within:shadow-[0_0_0_4px_var(--glow)]"
    >
      <textarea
        ref={ref}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            onSubmit();
          }
        }}
        rows={1}
        maxLength={1000}
        aria-label="Question"
        placeholder="Ask anything about your data… e.g. Which genres sell the most tracks?"
        className="block w-full resize-none bg-transparent px-3 pt-2.5 pb-1 text-base leading-relaxed outline-none placeholder:text-subtle"
      />
      <div className="flex flex-wrap items-center gap-2 px-1 pt-1">
        <div
          role="radiogroup"
          aria-label="Model"
          className="inline-flex rounded-lg bg-surface-2 p-0.5 text-[13px]"
        >
          {PROVIDERS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              role="radio"
              aria-checked={provider === id}
              disabled={busy}
              onClick={() => onProviderChange(id)}
              title={models?.[id]}
              className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 transition disabled:opacity-60 ${
                provider === id
                  ? "bg-surface text-foreground shadow-sm"
                  : "text-muted hover:text-foreground"
              }`}
            >
              <Icon className="size-3.5" />
              {label}
            </button>
          ))}
        </div>
        {models && (
          <span className="hidden max-w-[16rem] truncate font-mono text-[11px] text-subtle md:inline">
            {models[provider]}
          </span>
        )}
        <span className="ml-auto hidden text-[11px] text-subtle sm:inline">
          <kbd className="font-sans">Enter</kbd> to ask ·{" "}
          <kbd className="font-sans">Shift+Enter</kbd> new line
        </span>
        <button
          type="submit"
          disabled={busy || !value.trim()}
          aria-label="Ask"
          className="ml-auto grid size-9 place-items-center rounded-lg bg-accent text-on-accent shadow-sm transition hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40 sm:ml-0"
        >
          <ArrowUp className="size-4.5" strokeWidth={2.5} />
        </button>
      </div>
    </form>
  );
}
