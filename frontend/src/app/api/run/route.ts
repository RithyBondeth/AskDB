import { forward } from "@/lib/backend";

export async function POST(request: Request) {
  return forward("/api/run", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: await request.text(),
  });
}
