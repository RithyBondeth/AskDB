import { forward, withClientHeaders } from "@/lib/backend";

export async function GET(request: Request) {
  return forward("/api/health", { headers: withClientHeaders(request) });
}
