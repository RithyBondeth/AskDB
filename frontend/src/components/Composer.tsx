"use client";

import { ArrowUp, Bot, CornerDownRight, Cpu, Gift, Square } from "lucide-react";
import { type RefObject, useEffect } from "react";

import type { Provider } from "@/lib/types";

const PROVIDERS: { id: Provider; label: string; icon: typeof Bot; setup: string }[] = [
  {
    id: "free",
    label: "Free",
    icon: Gift,
    setup: "Free Gemini key: aistudio.google.com/apikey → ASKDB_FREE_API_KEY in backend/.env",
  },
  { id: "claude", label: "Claude", icon: Bot, setup: "Set ANTHROPIC_API_KEY in backend/.env" },
  { id: "local", label: "Open model", icon: Cpu, setup: "Runs on your machine with Ollama" },
];

export default function Composer({
  inputRef,
  value,
  onChange,
  onSubmit,
  onStop,
  provider,
  onProviderChange,
  models,
  configured,
  busy,
  followUpTo,
  example,
}: {
  inputRef: RefObject<HTMLTextAreaElement | null>;
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  onStop: () => void;
  provider: Provider;
  onProviderChange: (p: Provider) => void;
  models: Record<Provider, string> | null;
  configured: Record<Provider, boolean> | null;
  busy: boolean;
  followUpTo: string | null;
  example?: string;
}) {
  // Grow with content, up to a few lines.
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [value, inputRef]);

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
      className="card p-2.5 transition focus-within:shadow-[6px_6px_0_var(--ink)]"
    >
      {followUpTo && (
        <p className="flex items-center gap-1.5 truncate px-3 pt-1.5 text-xs text-subtle">
          <CornerDownRight className="size-3 shrink-0" />
          Follow-ups build on this conversation · last: “{followUpTo}”
        </p>
      )}
      <textarea
        ref={inputRef}
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
        placeholder={
          followUpTo
            ? "Ask a follow-up… e.g. only for 2012"
            : `Ask anything about your data…${example ? ` e.g. ${example}` : ""}`
        }
        className="block w-full resize-none bg-transparent px-3 pt-2.5 pb-1 text-[17px] leading-relaxed outline-none placeholder:text-subtle"
      />
      <div className="flex flex-wrap items-center gap-2 px-1 pt-1">
        <div
          role="radiogroup"
          aria-label="Model"
          className="sketch-sm inline-flex bg-surface-2 p-0.5 text-[13px]"
        >
          {PROVIDERS.map(({ id, label, icon: Icon, setup }) => {
            const ready = configured?.[id] ?? true;
            return (
              <button
                key={id}
                type="button"
                role="radio"
                aria-checked={provider === id}
                disabled={busy}
                onClick={() => onProviderChange(id)}
                title={ready ? models?.[id] : `Not set up yet. ${setup}`}
                className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 transition disabled:opacity-60 ${
                  provider === id
                    ? "bg-highlight font-medium text-[#1d1b19]"
                    : "text-muted hover:text-foreground"
                } ${ready ? "" : "line-through decoration-dotted opacity-60"}`}
              >
                <Icon className="size-3.5" />
                {label}
              </button>
            );
          })}
        </div>
        {configured && !configured[provider] ? (
          <span className="max-w-[22rem] truncate text-[11px] text-danger">
            Not set up: {PROVIDERS.find((p) => p.id === provider)?.setup}
          </span>
        ) : (
          models && (
            <span className="hidden max-w-[16rem] truncate font-mono text-[11px] text-subtle md:inline">
              {models[provider].split("/").at(-1)}
            </span>
          )
        )}
        <span className="ml-auto hidden text-[11px] text-subtle sm:inline">
          <kbd className="font-sans">↵</kbd> ask · <kbd className="font-sans">⇧↵</kbd> new line ·{" "}
          <kbd className="font-sans">⌘K</kbd> commands
        </span>
        {busy ? (
          <button
            type="button"
            onClick={onStop}
            aria-label="Stop"
            title="Stop"
            className="btn-paper ml-auto grid size-10 place-items-center sm:ml-0"
          >
            <Square className="size-3.5" fill="currentColor" />
          </button>
        ) : (
          <button
            type="submit"
            disabled={!value.trim()}
            aria-label="Ask"
            className="btn-ink ml-auto grid size-10 place-items-center sm:ml-0"
          >
            <ArrowUp className="size-5" strokeWidth={2.75} />
          </button>
        )}
      </div>
    </form>
  );
}
