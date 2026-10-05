import { forward, withClientHeaders } from "@/lib/backend";

export async function POST(request: Request, ctx: RouteContext<"/api/history/[id]/share">) {
  const { id } = await ctx.params;
  return forward(`/api/history/${encodeURIComponent(id)}/share`, {
    method: "POST",
    headers: withClientHeaders(request, { "content-type": "application/json" }),
    body: await request.text(),
  });
}
