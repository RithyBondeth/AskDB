const BACKEND_URL = process.env.ASKDB_API_URL ?? "http://127.0.0.1:8000";

// Generation plus up to two self-correction rounds can take a while.
export const maxDuration = 300;

// Pass the backend's Server-Sent Events straight through, unbuffered.
export async function POST(request: Request) {
  try {
    const res = await fetch(`${BACKEND_URL}/api/ask/stream`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: await request.text(),
      cache: "no-store",
    });
    return new Response(res.body, {
      status: res.status,
      headers: {
        "content-type": res.headers.get("content-type") ?? "text/event-stream",
        "cache-control": "no-cache, no-transform",
        "x-accel-buffering": "no",
      },
    });
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
