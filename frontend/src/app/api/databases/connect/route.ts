import { forward, withClientHeaders } from "@/lib/backend";

export async function POST(request: Request) {
  return forward("/api/databases/connect", {
    method: "POST",
    headers: withClientHeaders(request, { "content-type": "application/json" }),
    body: await request.text(),
  });
}
