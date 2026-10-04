import { afterEach, describe, expect, it, vi } from "vitest";
import { askStream } from "@/lib/stream";
import type { StreamEvent } from "@/lib/types";

afterEach(() => vi.unstubAllGlobals());

/** A fetch that answers with these body chunks (split anywhere, like a real network). */
function serve(chunks: string[], init: ResponseInit = {}) {
  const body = new ReadableStream({
    start(controller) {
      for (const c of chunks) controller.enqueue(new TextEncoder().encode(c));
      controller.close();
    },
  });
  const fetch = vi.fn(async () => new Response(body, init));
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

const sse = { headers: { "content-type": "text/event-stream" } };
const result = { sql: "SELECT 1", rows: [[1]] };
const opts = (events: StreamEvent[] = []) => ({
  question: "q",
  provider: "free" as const,
  database: "sample",
  context: [],
  onEvent: (e: StreamEvent) => events.push(e),
});

describe("askStream", () => {
  it("parses events split across chunks and skips keepalives", async () => {
    const msg = `data: ${JSON.stringify({ type: "stage", stage: "generate" })}\n\n`;
    const done = `data: ${JSON.stringify({ type: "result", data: result })}\n\n`;
    serve(
      [msg.slice(0, 10), msg.slice(10) + ": keepalive\n\n", done.slice(0, 7), done.slice(7)],
      sse,
    );
    const events: StreamEvent[] = [];
    await expect(askStream(opts(events))).resolves.toEqual(result);
    expect(events.map((e) => e.type)).toEqual(["stage", "result"]);
  });

  it("sends the browser id and the user's key", async () => {
    const fetch = serve([`data: ${JSON.stringify({ type: "result", data: result })}\n\n`], sse);
    await askStream({ ...opts(), apiKey: "k" });
    const headers = (fetch.mock.calls[0] as unknown as [string, RequestInit])[1].headers;
    expect(headers).toMatchObject({ "x-askdb-api-key": "k" });
    expect(Object.keys(headers as object)).toContain("x-askdb-owner");
  });

  it("rejects with the error event's detail", async () => {
    const detail = { message: "nope", attempts: [] };
    serve([`data: ${JSON.stringify({ type: "error", status: 422, detail })}\n\n`], sse);
    await expect(askStream(opts())).rejects.toEqual(detail);
  });

  it("rejects with the message from a plain JSON error", async () => {
    serve([JSON.stringify({ detail: { message: "That database no longer exists." } })], {
      status: 404,
      headers: { "content-type": "application/json" },
    });
    await expect(askStream(opts())).rejects.toMatchObject({
      message: "That database no longer exists.",
    });
  });

  it("rejects when the stream ends without an answer", async () => {
    serve([": keepalive\n\n"], sse);
    await expect(askStream(opts())).rejects.toMatchObject({ message: /closed before/ });
  });
});
