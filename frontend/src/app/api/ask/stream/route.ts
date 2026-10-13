import { withClientHeaders } from "@/lib/backend";

const BACKEND_URL = process.env.ASKDB_API_URL ?? "http://127.0.0.1:8000";

// Generation plus up to two self-correction rounds can take a while.
export const maxDuration = 300;

// Pass the backend's Server-Sent Events straight through, unbuffered.
export async function POST(request: Request) {
  try {
    const res = await fetch(`${BACKEND_URL}/api/ask/stream`, {
      method: "POST",
      headers: withClientHeaders(request, { "content-type": "application/json" }),
      body: await request.text(),
      cache: "no-store",
      // When the browser hangs up (Stop, new chat, closed tab), hang up on the
      // backend too, so it stops calling the model.
      signal: request.signal,
    });
    const headers: Record<string, string> = {
      "content-type": res.headers.get("content-type") ?? "text/event-stream",
      "cache-control": "no-cache, no-transform",
      "x-accel-buffering": "no",
    };
    // Rate-limited (429) answers say when to try again.
    const retryAfter = res.headers.get("retry-after");
    if (retryAfter) headers["retry-after"] = retryAfter;
    return new Response(res.body, { status: res.status, headers });
  } catch {
    return Response.json(
      {
        detail: {
          message: `Cannot reach the AskDB API at ${BACKEND_URL}. Is the backend running?`,
          attempts: [],
        },
      },
      { status: 503 },
    );
  }
}
