import { forward } from "@/lib/backend";

export async function GET() {
  return forward("/api/databases");
}

// Multipart upload: pass the body and its boundary header through unchanged.
export async function POST(request: Request) {
  return forward("/api/databases", {
    method: "POST",
    headers: { "content-type": request.headers.get("content-type") ?? "" },
    body: await request.arrayBuffer(),
  });
}
