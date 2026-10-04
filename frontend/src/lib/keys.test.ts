import { afterEach, describe, expect, it, vi } from "vitest";
import { keyFor, loadKeys, maskKey, saveKeys } from "@/lib/keys";
import { stubLocalStorage } from "@/lib/test-utils";

afterEach(() => vi.unstubAllGlobals());

describe("keys", () => {
  it("round-trips through storage, trimming and dropping blanks", () => {
    const data = stubLocalStorage();
    saveKeys({ free: "AIzaKEY" });
    expect(loadKeys()).toEqual({ free: "AIzaKEY" });

    data.set("askdb:api-keys", JSON.stringify({ free: "  x  ", claude: " ", other: "y" }));
    expect(loadKeys()).toEqual({ free: "x" });

    saveKeys({});
    expect(data.has("askdb:api-keys")).toBe(false);
  });

  it("survives bad JSON and blocked storage", () => {
    stubLocalStorage().set("askdb:api-keys", "{not json");
    expect(loadKeys()).toEqual({});
    stubLocalStorage({ broken: true });
    expect(loadKeys()).toEqual({});
    expect(() => saveKeys({ free: "k" })).not.toThrow();
  });

  it("never uses a key for the local model", () => {
    expect(keyFor({ free: "f", claude: "c" }, "claude")).toBe("c");
    expect(keyFor({ free: "f" }, "local")).toBeUndefined();
  });

  it("masks keys", () => {
    expect(maskKey("AIzaSyAbcdefghij9Qk")).toBe("AIza…j9Qk");
    expect(maskKey("short")).toBe("••••");
  });
});
