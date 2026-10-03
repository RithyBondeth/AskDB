"use client";

import { ArrowUp, Bot, Check, ChevronDown, Cpu, Gift, Square } from "lucide-react";
import { type RefObject, useEffect, useRef, useState } from "react";

import type { Provider } from "@/lib/types";

const PROVIDERS: { id: Provider; label: string; icon: typeof Bot; note: string; setup: string }[] =
  [
    {
      id: "free",
      label: "Free",
      icon: Gift,
      note: "Gemini free tier",
      setup: "Add a free Gemini key as ASKDB_FREE_API_KEY in backend/.env",
    },
    {
      id: "claude",
      label: "Claude",
      icon: Bot,
      note: "Most accurate",
      setup: "Add ANTHROPIC_API_KEY in backend/.env",
    },
    {
      id: "local",
      label: "Open model",
      icon: Cpu,
      note: "Runs on your machine",
      setup: "Install Ollama and pull the model",
    },
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
}) {
  // Grow with content, up to a few lines.
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [value, inputRef]);

  const notReady = configured ? !configured[provider] : false;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
      className="card p-2 transition focus-within:border-ink"
    >
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
        placeholder={followUpTo ? "Ask a follow-up…" : "Ask a question about your data…"}
        className="block w-full resize-none bg-transparent px-3 pt-2.5 pb-1 text-[17px] leading-relaxed outline-none placeholder:text-subtle"
      />
      <div className="flex items-center gap-2 px-1 pt-1">
        <ModelMenu
          provider={provider}
          onChange={onProviderChange}
          models={models}
          configured={configured}
          disabled={busy}
        />
        {notReady && (
          <span className="truncate text-xs text-danger">
            {PROVIDERS.find((p) => p.id === provider)?.setup}
          </span>
        )}
        {busy ? (
          <button
            type="button"
            onClick={onStop}
            aria-label="Stop"
            title="Stop"
            className="btn-paper ml-auto grid size-10 shrink-0 place-items-center"
          >
            <Square className="size-3.5" fill="currentColor" />
          </button>
        ) : (
          <button
            type="submit"
            disabled={!value.trim()}
            aria-label="Ask"
            title="Ask (Enter)"
            className="btn-ink ml-auto grid size-10 shrink-0 place-items-center"
          >
            <ArrowUp className="size-5" strokeWidth={2.75} />
          </button>
        )}
      </div>
    </form>
  );
}

/** One small button showing the current model; the choices open in a menu. */
function ModelMenu({
  provider,
  onChange,
  models,
  configured,
  disabled,
}: {
  provider: Provider;
  onChange: (p: Provider) => void;
  models: Record<Provider, string> | null;
  configured: Record<Provider, boolean> | null;
  disabled: boolean;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const current = PROVIDERS.find((p) => p.id === provider) ?? PROVIDERS[0];
  const CurrentIcon = current.icon;

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative shrink-0">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`Model: ${current.label}`}
        title={models?.[provider]}
        className="inline-flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-sm text-muted transition hover:bg-surface-2 hover:text-foreground disabled:opacity-50"
      >
        <CurrentIcon className="size-4" />
        {current.label}
        <ChevronDown className={`size-3.5 transition ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <ul
          role="listbox"
          aria-label="Model"
          className="card animate-pop-in absolute bottom-10 left-0 z-40 w-64 p-1.5"
        >
          {PROVIDERS.map(({ id, label, icon: Icon, note, setup }) => {
            const ready = configured?.[id] ?? true;
            const selected = id === provider;
            return (
              <li key={id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={selected}
                  onClick={() => {
                    onChange(id);
                    setOpen(false);
                  }}
                  className="flex w-full items-start gap-2.5 rounded-lg px-2.5 py-2 text-left hover:bg-surface-2"
                >
                  <Icon className="mt-0.5 size-4 shrink-0 text-muted" />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-semibold">{label}</span>
                    <span className={`block text-xs ${ready ? "text-subtle" : "text-danger"}`}>
                      {ready ? note : `Not set up. ${setup}`}
                    </span>
                  </span>
                  {selected && <Check className="mt-0.5 size-4 shrink-0 text-accent" />}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
