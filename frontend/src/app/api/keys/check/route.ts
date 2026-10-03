import { forward, withUserKey } from "@/lib/backend";

export async function POST(request: Request) {
  return forward("/api/keys/check", {
    method: "POST",
    headers: withUserKey(request, { "content-type": "application/json" }),
    body: await request.text(),
  });
}
