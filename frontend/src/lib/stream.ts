import { KEY_HEADER } from "@/lib/keys";
import type { AskError, AskResponse, DatabaseInfo, Provider, StreamEvent } from "@/lib/types";

export interface AskOptions {
  question: string;
  provider: Provider;
  database: string;
  context: { question: string; sql: string }[];
  /** The user's own key for `provider`, if they added one. */
  apiKey?: string;
  onEvent: (event: StreamEvent) => void;
  signal?: AbortSignal;
}

/** POST /api/ask/stream and feed each Server-Sent Event to onEvent. Resolves with the
 *  final result, or rejects with an AskError. */
export async function askStream({
  question,
  provider,
  database,
  context,
  apiKey,
  onEvent,
  signal,
}: AskOptions): Promise<AskResponse> {
  let res: Response;
  try {
    res = await fetch("/api/ask/stream", {
      method: "POST",
      headers: { "content-type": "application/json", ...(apiKey ? { [KEY_HEADER]: apiKey } : {}) },
      body: JSON.stringify({ question, provider, context, database }),
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

export async function runSql(sql: string, database: string): Promise<AskResponse> {
  let res: Response;
  try {
    res = await fetch("/api/run", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ sql, database }),
    });
  } catch {
    throw { message: "Network error: could not reach the server.", attempts: [] } as AskError;
  }
  if (!res.ok) throw await errorFrom(res);
  return (await res.json()) as AskResponse;
}

/** Upload files as a new database, reporting upload progress (0-1). */
export function uploadDatabase(
  files: File[],
  name: string,
  onProgress: (fraction: number) => void,
): Promise<DatabaseInfo> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f, f.name));
    if (name.trim()) form.append("name", name.trim());
    // XHR rather than fetch: it reports upload progress.
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/databases");
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onerror = () => reject({ message: "Network error during upload.", attempts: [] });
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        // not JSON
      }
      if (xhr.status >= 200 && xhr.status < 300) return resolve(body as DatabaseInfo);
      const detail = (body as { detail?: { message?: string } } | null)?.detail;
      reject({ message: detail?.message ?? `Upload failed (${xhr.status}).`, attempts: [] });
    };
    xhr.send(form);
  });
}

export async function deleteDatabase(id: string): Promise<void> {
  const res = await fetch(`/api/databases/${encodeURIComponent(id)}`, { method: "DELETE" });
  if (!res.ok) throw await errorFrom(res);
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

/** Try a key without spending tokens (the backend lists the provider's models). */
export async function checkKey(
  provider: "free" | "claude",
  key: string,
): Promise<{ ok: boolean; message: string }> {
  try {
    const res = await fetch("/api/keys/check", {
      method: "POST",
      headers: { "content-type": "application/json", [KEY_HEADER]: key },
      body: JSON.stringify({ provider }),
    });
    if (!res.ok) return { ok: false, message: (await errorFrom(res)).message };
    return (await res.json()) as { ok: boolean; message: string };
  } catch {
    return { ok: false, message: "Network error: could not reach the server." };
  }
}
