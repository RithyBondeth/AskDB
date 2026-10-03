import { forward } from "@/lib/backend";

export async function GET() {
  return forward("/api/health");
}
