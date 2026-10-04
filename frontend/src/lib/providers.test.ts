import { afterEach, describe, expect, it, vi } from "vitest";
import { loadKeys } from "@/lib/keys";
import { loadChoice, saveChoice } from "@/lib/modelChoice";
import { effectiveModel, isProvider, PROVIDERS, shortModel } from "@/lib/providers";
import { stubLocalStorage } from "@/lib/test-utils";
import type { ModelsResponse } from "@/lib/types";

afterEach(() => vi.unstubAllGlobals());

const list = (ids: string[], def = ids[0]): ModelsResponse => ({
  provider: "groq",
  default: def,
  models: ids.map((id) => ({ id, label: id })),
  source: "live",
  error: null,
});

describe("effectiveModel", () => {
  it("keeps the user's pick while the provider still offers it", () => {
    expect(effectiveModel("b", list(["a", "b"]), "x")).toBe("b");
  });
  it("falls back to the list's default when the pick isn't offered", () => {
    // e.g. the user removed their key, so only the server's models remain
    expect(effectiveModel("gone", list(["a", "b"], "b"), "x")).toBe("b");
  });
  it("uses the pick, then the server default, before the list loads", () => {
    expect(effectiveModel("b", undefined, "x")).toBe("b");
    expect(effectiveModel(undefined, undefined, "x")).toBe("x");
  });
});

describe("providers", () => {
  it("lists every backend provider once, local last and keyless", () => {
    const ids = PROVIDERS.map((p) => p.id);
    expect(new Set(ids)).toEqual(
      new Set(["free", "claude", "groq", "openrouter", "openai", "local"]),
    );
    expect(ids.at(-1)).toBe("local");
    expect(PROVIDERS.find((p) => p.id === "local")?.key).toBeUndefined();
    for (const p of PROVIDERS.filter((p) => p.id !== "local")) {
      expect(p.key?.url).toMatch(/^https:\/\//);
    }
  });
  it("recognises provider ids", () => {
    expect(isProvider("groq")).toBe(true);
    expect(isProvider("gpt")).toBe(false);
    expect(isProvider(3)).toBe(false);
  });
  it("shortens model paths for display", () => {
    expect(shortModel("hf.co/org/Model-GGUF:Q4_K_M")).toBe("Model-GGUF:Q4_K_M");
    expect(shortModel("claude-opus-5-5")).toBe("claude-opus-5-5");
  });
});

describe("stored choices", () => {
  it("round-trips and drops unknown providers", () => {
    const data = stubLocalStorage();
    saveChoice({ provider: "groq", models: { groq: "llama", claude: "claude-haiku-4-5" } });
    expect(loadChoice()).toEqual({
      provider: "groq",
      models: { groq: "llama", claude: "claude-haiku-4-5" },
    });
    data.set("askdb:model-choice", JSON.stringify({ provider: "gpt", models: { gpt: "x" } }));
    expect(loadChoice()).toEqual({ provider: undefined, models: {} });
  });
  it("survives blocked storage", () => {
    stubLocalStorage({ broken: true });
    expect(loadChoice()).toEqual({ models: {} });
    expect(() => saveChoice({ models: {} })).not.toThrow();
  });
  it("loads keys for the new providers", () => {
    stubLocalStorage().set(
      "askdb:api-keys",
      JSON.stringify({ groq: "gsk_1", openrouter: "sk-or-1", openai: "sk-1", local: "no" }),
    );
    expect(loadKeys()).toEqual({ groq: "gsk_1", openrouter: "sk-or-1", openai: "sk-1" });
  });
});
