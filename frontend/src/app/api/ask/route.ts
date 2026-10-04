import { forward, withClientHeaders } from "@/lib/backend";

// Generation plus up to two self-correction rounds can take a while.
export const maxDuration = 120;

export async function POST(request: Request) {
  return forward("/api/ask", {
    method: "POST",
    headers: withClientHeaders(request, { "content-type": "application/json" }),
    body: await request.text(),
  });
}
