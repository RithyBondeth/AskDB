// The user's own model API keys. They live only in this browser (localStorage) and
// are sent with each question to the AskDB backend, which uses them for that one
// request and never stores them.
import { PROVIDERS } from "@/lib/providers";
import type { Provider } from "@/lib/types";

export type KeyProvider = Exclude<Provider, "local">;
export type ApiKeys = Partial<Record<KeyProvider, string>>;

const STORAGE_KEY = "askdb:api-keys";
export const KEY_HEADER = "x-askdb-api-key";

export function loadKeys(): ApiKeys {
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
    const keys: ApiKeys = {};
    for (const { id, key } of PROVIDERS) {
      if (!key || id === "local") continue;
      if (typeof raw[id] === "string" && raw[id].trim()) keys[id] = raw[id].trim();
    }
    return keys;
  } catch {
    return {};
  }
}

export function saveKeys(keys: ApiKeys) {
  try {
    if (Object.keys(keys).length) localStorage.setItem(STORAGE_KEY, JSON.stringify(keys));
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Storage blocked (private mode): keys last until the tab closes.
  }
}

export function keyFor(keys: ApiKeys, provider: Provider): string | undefined {
  return provider === "local" ? undefined : keys[provider];
}

/** "AIza…x9Qk": enough to recognise a saved key without showing it. */
export function maskKey(key: string): string {
  return key.length <= 10 ? "••••" : `${key.slice(0, 4)}…${key.slice(-4)}`;
}
