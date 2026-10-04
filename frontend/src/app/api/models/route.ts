import { forward, withClientHeaders } from "@/lib/backend";

export async function GET(request: Request) {
  const provider = new URL(request.url).searchParams.get("provider") ?? "";
  return forward(`/api/models?provider=${encodeURIComponent(provider)}`, {
    headers: withClientHeaders(request),
  });
}
