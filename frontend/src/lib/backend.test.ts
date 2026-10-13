import { afterEach, describe, expect, it, vi } from "vitest";
import { forward, withClientHeaders } from "@/lib/backend";

describe("withClientHeaders", () => {
  it("forwards only the model key, browser id and client address", () => {
    const request = new Request("http://x", {
      headers: {
        "x-askdb-api-key": "k",
        "x-askdb-owner": "o",
        "x-forwarded-for": "203.0.113.7",
        cookie: "secret=1",
      },
    });
    expect(withClientHeaders(request, { "content-type": "application/json" })).toEqual({
      "content-type": "application/json",
      "x-askdb-api-key": "k",
      "x-askdb-owner": "o",
      "x-forwarded-for": "203.0.113.7",
    });
    expect(withClientHeaders(new Request("http://x"))).toEqual({});
  });
});

describe("forward", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("passes a rate limit's status, message and Retry-After through", async () => {
    const detail = { detail: { message: "Too many requests.", attempts: [] } };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json(detail, { status: 429, headers: { "retry-after": "42", "x-other": "no" } }),
      ),
    );
    const res = await forward("/api/run", { method: "POST" });
    expect(res.status).toBe(429);
    expect(res.headers.get("retry-after")).toBe("42");
    expect(res.headers.get("x-other")).toBeNull();
    expect(await res.json()).toEqual(detail);
  });
});
