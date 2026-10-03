import type { AskError, AskResponse, Provider, StreamEvent } from "@/lib/types";

export interface AskOptions {
  question: string;
  provider: Provider;
  context: { question: string; sql: string }[];
  onEvent: (event: StreamEvent) => void;
  signal?: AbortSignal;
}

/** POST /api/ask/stream and feed each Server-Sent Event to onEvent. Resolves with the
 *  final result, or rejects with an AskError. */
export async function askStream({
  question,
  provider,
  context,
  onEvent,
  signal,
}: AskOptions): Promise<AskResponse> {
  let res: Response;
  try {
    res = await fetch("/api/ask/stream", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ question, provider, context }),
      signal,
    });
  } catch {
    throw { message: "Network error: could not reach the server.", attempts: [] } as AskError;
  }

  // Request-level failures (bad input, backend down) come back as plain JSON.
  if (!res.ok || !res.headers.get("content-type")?.includes("text/event-stream") || !res.body) {
    throw await errorFrom(res);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let split: number;
    while ((split = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, split);
      buffer = buffer.slice(split + 2);
      const line = chunk.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      const event = JSON.parse(line.slice(6)) as StreamEvent;
      onEvent(event);
      if (event.type === "result") return event.data;
      if (event.type === "error") throw event.detail;
    }
  }
  throw { message: "The connection closed before an answer arrived.", attempts: [] } as AskError;
}

export async function runSql(sql: string): Promise<AskResponse> {
  let res: Response;
  try {
    res = await fetch("/api/run", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ sql }),
    });
  } catch {
    throw { message: "Network error: could not reach the server.", attempts: [] } as AskError;
  }
  if (!res.ok) throw await errorFrom(res);
  return (await res.json()) as AskResponse;
}

async function errorFrom(res: Response): Promise<AskError> {
  try {
    const body = await res.json();
    const detail = body?.detail;
    if (detail && typeof detail === "object" && "message" in detail) {
      return { message: String(detail.message), attempts: detail.attempts ?? [] };
    }
    if (Array.isArray(detail)) {
      // FastAPI validation error
      return { message: detail.map((d) => d.msg).join("; "), attempts: [] };
    }
  } catch {
    // not JSON
  }
  return { message: `Request failed (${res.status}).`, attempts: [] };
}
