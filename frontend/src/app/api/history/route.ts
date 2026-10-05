import { forward, withClientHeaders } from "@/lib/backend";

export async function GET(request: Request) {
  const { search } = new URL(request.url);
  return forward(`/api/history${search}`, { headers: withClientHeaders(request) });
}

export async function DELETE(request: Request) {
  const { search } = new URL(request.url);
  return forward(`/api/history${search}`, {
    method: "DELETE",
    headers: withClientHeaders(request),
  });
}
