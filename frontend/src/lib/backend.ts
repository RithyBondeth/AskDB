// Server-only helper: the browser talks to Next.js route handlers, which
// forward to the Python API. This keeps the backend URL private and avoids CORS.

import { KEY_HEADER } from "@/lib/keys";

const BACKEND_URL = process.env.ASKDB_API_URL ?? "http://127.0.0.1:8000";

export async function forward(path: string, init?: RequestInit): Promise<Response> {
  try {
    const res = await fetch(`${BACKEND_URL}${path}`, { ...init, cache: "no-store" });
    const body = await res.text();
    return new Response(body, {
      status: res.status,
      headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
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

/** Headers for the backend, plus the user's own model key if the browser sent one. */
export function withUserKey(request: Request, headers: Record<string, string>) {
  const key = request.headers.get(KEY_HEADER);
  return key ? { ...headers, [KEY_HEADER]: key } : headers;
}
