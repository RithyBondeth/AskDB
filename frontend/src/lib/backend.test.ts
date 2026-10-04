import { describe, expect, it } from "vitest";
import { withClientHeaders } from "@/lib/backend";

describe("withClientHeaders", () => {
  it("forwards only the model key and browser id", () => {
    const request = new Request("http://x", {
      headers: { "x-askdb-api-key": "k", "x-askdb-owner": "o", cookie: "secret=1" },
    });
    expect(withClientHeaders(request, { "content-type": "application/json" })).toEqual({
      "content-type": "application/json",
      "x-askdb-api-key": "k",
      "x-askdb-owner": "o",
    });
    expect(withClientHeaders(new Request("http://x"))).toEqual({});
  });
});
