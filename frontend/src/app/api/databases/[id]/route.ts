import { forward, withClientHeaders } from "@/lib/backend";

export async function DELETE(request: Request, ctx: RouteContext<"/api/databases/[id]">) {
  const { id } = await ctx.params;
  return forward(`/api/databases/${encodeURIComponent(id)}`, {
    method: "DELETE",
    headers: withClientHeaders(request),
  });
}
