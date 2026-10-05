import { withClientHeaders } from "@/lib/backend";

const BACKEND_URL = process.env.ASKDB_API_URL ?? "http://127.0.0.1:8000";

// A full export can be large: stream the backend's CSV through instead of buffering it.
export async function POST(request: Request) {
  try {
    const res = await fetch(`${BACKEND_URL}/api/export`, {
      method: "POST",
      headers: withClientHeaders(request, { "content-type": "application/json" }),
      body: await request.text(),
      cache: "no-store",
      signal: request.signal,
    });
    const headers: Record<string, string> = {
      "content-type": res.headers.get("content-type") ?? "text/csv",
    };
    const disposition = res.headers.get("content-disposition");
    if (disposition) headers["content-disposition"] = disposition;
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
