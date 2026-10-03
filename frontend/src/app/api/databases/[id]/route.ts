import { forward } from "@/lib/backend";

export async function DELETE(_request: Request, ctx: RouteContext<"/api/databases/[id]">) {
  const { id } = await ctx.params;
  return forward(`/api/databases/${encodeURIComponent(id)}`, { method: "DELETE" });
}
