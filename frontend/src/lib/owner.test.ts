import { afterEach, describe, expect, it, vi } from "vitest";
import { stubLocalStorage } from "@/lib/test-utils";

// The backend's rule for browser ids (backend/askdb/sources.py, _OWNER).
const BACKEND_RULE = /^[A-Za-z0-9_-]{16,128}$/;

async function freshOwner() {
  vi.resetModules(); // owner.ts caches a fallback id at module level
  return import("@/lib/owner");
}

afterEach(() => vi.unstubAllGlobals());

describe("ownerId", () => {
  it("is created once, kept in storage, and accepted by the backend", async () => {
    const data = stubLocalStorage();
    const { ownerId, ownerHeaders, OWNER_HEADER } = await freshOwner();
    const id = ownerId();
    expect(id).toMatch(BACKEND_RULE);
    expect(ownerId()).toBe(id);
    expect(data.get("askdb:owner")).toBe(id);
    expect(ownerHeaders({ a: "b" })).toEqual({ a: "b", [OWNER_HEADER]: id });
  });

  it("falls back to one id per tab when storage is blocked", async () => {
    stubLocalStorage({ broken: true });
    const { ownerId } = await freshOwner();
    const id = ownerId();
    expect(id).toMatch(BACKEND_RULE);
    expect(ownerId()).toBe(id);
  });
});

describe("setOwnerId", () => {
  it("adopts a valid sync code and rejects anything else", async () => {
    const data = stubLocalStorage();
    const { ownerId, setOwnerId } = await freshOwner();
    const code = "other-device-0123456789";
    expect(setOwnerId("not valid!")).toBe(false);
    expect(setOwnerId(`  ${code} `)).toBe(true);
    expect(data.get("askdb:owner")).toBe(code);
    expect(ownerId()).toBe(code);
  });
});
