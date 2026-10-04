"use client";

import { ArrowUp, CornerDownRight, Square } from "lucide-react";
import { type RefObject, useEffect } from "react";

import ModelPicker from "@/components/ModelPicker";
import type { ModelsResponse, Provider } from "@/lib/types";

export default function Composer({
  inputRef,
  value,
  onChange,
  onSubmit,
  onStop,
  provider,
  onProviderChange,
  model,
  onModelChange,
  modelList,
  modelsLoading,
  configured,
  onAddKey,
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
  model: string | undefined;
  onModelChange: (model: string) => void;
  modelList: ModelsResponse | undefined;
  modelsLoading: boolean;
  configured: Record<Provider, boolean> | null;
  onAddKey: () => void;
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
        <ModelPicker
          provider={provider}
          onProviderChange={onProviderChange}
          model={model}
          onModelChange={onModelChange}
          list={modelList}
          loading={modelsLoading}
          configured={configured}
          disabled={busy}
          onAddKey={onAddKey}
        />
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
