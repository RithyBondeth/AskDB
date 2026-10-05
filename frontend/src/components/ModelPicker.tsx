"use client";

import { ChevronDown, KeyRound, Loader2 } from "lucide-react";

import { modelOptionLabel, PROVIDERS, providerInfo } from "@/lib/providers";
import type { ModelsResponse, Provider } from "@/lib/types";

/** Two compact menus under the question box: which provider, then which of its models. */
export default function ModelPicker({
  provider,
  onProviderChange,
  model,
  onModelChange,
  list,
  loading,
  configured,
  disabled,
  onAddKey,
}: {
  provider: Provider;
  onProviderChange: (p: Provider) => void;
  /** The model that will be asked. */
  model: string | undefined;
  onModelChange: (model: string) => void;
  list: ModelsResponse | undefined;
  loading: boolean;
  configured: Record<Provider, boolean> | null;
  disabled: boolean;
  onAddKey: () => void;
}) {
  const info = providerInfo(provider);
  const ready = configured?.[provider] ?? true;
  const Icon = info.icon;
  // Keep the current model selectable while the list loads or if it isn't listed.
  const options = list?.models ?? [];
  const shown =
    model && !options.some((m) => m.id === model)
      ? [{ id: model, label: model, note: undefined }, ...options]
      : options;

  return (
    <div className="flex min-w-0 flex-wrap items-center gap-1.5 text-[13px]">
      <div className="sketch-sm relative inline-flex items-center bg-surface-2">
        <Icon className="pointer-events-none absolute left-2 size-3.5" />
        <select
          aria-label="Provider"
          value={provider}
          disabled={disabled}
          onChange={(e) => onProviderChange(e.target.value as Provider)}
          className="cursor-pointer appearance-none bg-transparent py-1 pr-6 pl-7 font-medium outline-none disabled:opacity-60"
        >
          {PROVIDERS.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
              {configured?.[p.id] === false ? " (needs key)" : ""}
            </option>
          ))}
        </select>
        <ChevronDown className="pointer-events-none absolute right-1.5 size-3.5 text-muted" />
      </div>

      {ready ? (
        <div className="sketch-sm relative inline-flex min-w-0 items-center bg-surface">
          <select
            aria-label="Model"
            value={model ?? ""}
            disabled={disabled || shown.length === 0}
            onChange={(e) => onModelChange(e.target.value)}
            title={model}
            className="max-w-[14rem] cursor-pointer appearance-none truncate bg-transparent py-1 pr-6 pl-2 font-mono text-[12px] outline-none disabled:opacity-60 sm:max-w-[18rem]"
          >
            {shown.map((m) => (
              <option key={m.id} value={m.id}>
                {modelOptionLabel(m)}
              </option>
            ))}
          </select>
          {loading ? (
            <Loader2 className="pointer-events-none absolute right-1.5 size-3.5 animate-spin text-muted" />
          ) : (
            <ChevronDown className="pointer-events-none absolute right-1.5 size-3.5 text-muted" />
          )}
        </div>
      ) : (
        <button
          type="button"
          onClick={onAddKey}
          className="inline-flex items-center gap-1 text-[12px] font-medium text-danger underline underline-offset-2"
        >
          <KeyRound className="size-3.5" />
          Add a {info.label.replace(/ \(.*\)/, "")} key
        </button>
      )}

      {ready && list?.error && (
        <span className="max-w-[16rem] truncate text-[11px] text-danger" title={list.error}>
          {list.error}
        </span>
      )}
      {ready && list?.source === "allowed" && !list.error && provider !== "local" && (
        <button
          type="button"
          onClick={onAddKey}
          className="hidden text-[11px] text-subtle underline-offset-2 hover:underline md:inline"
          title="With your own key you can pick from every model the provider offers you."
        >
          more with your key
        </button>
      )}
    </div>
  );
}
