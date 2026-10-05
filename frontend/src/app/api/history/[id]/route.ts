import { forward, withClientHeaders } from "@/lib/backend";

export async function GET(request: Request, ctx: RouteContext<"/api/history/[id]">) {
  const { id } = await ctx.params;
  return forward(`/api/history/${encodeURIComponent(id)}`, {
    headers: withClientHeaders(request),
  });
}

export async function DELETE(request: Request, ctx: RouteContext<"/api/history/[id]">) {
  const { id } = await ctx.params;
  return forward(`/api/history/${encodeURIComponent(id)}`, {
    method: "DELETE",
    headers: withClientHeaders(request),
  });
}
