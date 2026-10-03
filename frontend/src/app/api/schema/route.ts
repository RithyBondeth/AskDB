import { forward } from "@/lib/backend";

export async function GET(request: Request) {
  const database = new URL(request.url).searchParams.get("database");
  return forward(`/api/schema${database ? `?database=${encodeURIComponent(database)}` : ""}`);
}
