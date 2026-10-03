import { forward } from "@/lib/backend";

// Generation plus up to two self-correction rounds can take a while.
export const maxDuration = 120;

export async function POST(request: Request) {
  return forward("/api/ask", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: await request.text(),
  });
}
