// Shared helpers for the unit tests.
import { vi } from "vitest";

/** An in-memory localStorage; `broken` makes every call throw, like private mode. */
export function stubLocalStorage({ broken = false } = {}) {
  const data = new Map<string, string>();
  const fail = () => {
    throw new DOMException("blocked", "SecurityError");
  };
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => (broken ? fail() : (data.get(k) ?? null)),
    setItem: (k: string, v: string) => (broken ? fail() : void data.set(k, v)),
    removeItem: (k: string) => (broken ? fail() : void data.delete(k)),
  });
  return data;
}
