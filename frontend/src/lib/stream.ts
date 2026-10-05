import { KEY_HEADER, type KeyProvider } from "@/lib/keys";
import { ownerHeaders } from "@/lib/owner";
import type {
  AskError,
  AskResponse,
  DatabaseInfo,
  ModelsResponse,
  Provider,
  RowsPage,
  SavedAnswer,
  SavedAnswerSummary,
  StreamEvent,
} from "@/lib/types";

export interface AskOptions {
  question: string;
  provider: Provider;
  /** A model from /api/models; undefined uses the provider's default. */
  model?: string;
  database: string;
  context: { question: string; sql: string }[];
  /** The user's own key for `provider`, if they added one. */
  apiKey?: string;
  onEvent: (event: StreamEvent) => void;
  signal?: AbortSignal;
}

/** POST /api/ask/stream and feed each Server-Sent Event to onEvent. Resolves with the
 *  final result once the stream ends (after the `summary` event that follows the
 *  result), or rejects with an AskError. The result also reaches onEvent as soon as
 *  it arrives, so the UI can show it while the summary is written. */
export async function askStream({
  question,
  provider,
  model,
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
      headers: ownerHeaders({
        "content-type": "application/json",
        ...(apiKey ? { [KEY_HEADER]: apiKey } : {}),
      }),
      body: JSON.stringify({ question, provider, model, context, database }),
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
  let result = null as AskResponse | null; // (not narrowed to null inside the loop)
  try {
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
        if (event.type === "result") result = event.data;
        else if (event.type === "summary" && result) result = { ...result, summary: event.text };
        else if (event.type === "error") throw event.detail;
      }
    }
  } catch (err) {
    // Stopped or disconnected while the summary was being written: the answer stands.
    if (result) return result;
    throw err;
  }
  if (result) return result;
  throw { message: "The connection closed before an answer arrived.", attempts: [] } as AskError;
}

export async function runSql(sql: string, database: string): Promise<AskResponse> {
  let res: Response;
  try {
    res = await fetch("/api/run", {
      method: "POST",
      headers: ownerHeaders({ "content-type": "application/json" }),
      body: JSON.stringify({ sql, database }),
    });
  } catch {
    throw { message: "Network error: could not reach the server.", attempts: [] } as AskError;
  }
  if (!res.ok) throw await errorFrom(res);
  return (await res.json()) as AskResponse;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      method: "POST",
      headers: ownerHeaders({ "content-type": "application/json" }),
      body: JSON.stringify(body),
    });
  } catch {
    throw { message: "Network error: could not reach the server.", attempts: [] } as AskError;
  }
  if (!res.ok) throw await errorFrom(res);
  return (await res.json()) as T;
}

/** The next page of an answer's rows (the same SQL, re-run from `offset`). */
export function fetchRows(
  sql: string,
  database: string,
  offset: number,
  limit = 500,
): Promise<RowsPage> {
  return postJson<RowsPage>("/api/rows", { sql, database, offset, limit });
}

/** Download every row of an answer as CSV (the server caps very large exports). */
export async function exportCsv(sql: string, database: string, filename = "askdb-result.csv") {
  const res = await fetch("/api/export", {
    method: "POST",
    headers: ownerHeaders({ "content-type": "application/json" }),
    body: JSON.stringify({ sql, database }),
  });
  if (!res.ok) throw await errorFrom(res);
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** Add a live PostgreSQL or MySQL database by connection string. */
export function connectDatabase(url: string, name: string): Promise<DatabaseInfo> {
  return postJson<DatabaseInfo>("/api/databases/connect", {
    url,
    name: name.trim() || undefined,
  });
}

/** This browser's saved answers for a database, newest first. */
export async function listHistory(database: string): Promise<SavedAnswerSummary[]> {
  const res = await fetch(`/api/history?database=${encodeURIComponent(database)}`, {
    headers: ownerHeaders(),
  });
  if (!res.ok) throw await errorFrom(res);
  return ((await res.json()) as { answers: SavedAnswerSummary[] }).answers;
}

/** A saved answer: this browser's own, or a shared one. */
export async function getSavedAnswer(id: string): Promise<SavedAnswer> {
  const res = await fetch(`/api/history/${encodeURIComponent(id)}`, { headers: ownerHeaders() });
  if (!res.ok) throw await errorFrom(res);
  return (await res.json()) as SavedAnswer;
}

export async function deleteSavedAnswer(id: string): Promise<void> {
  const res = await fetch(`/api/history/${encodeURIComponent(id)}`, {
    method: "DELETE",
    headers: ownerHeaders(),
  });
  if (!res.ok) throw await errorFrom(res);
}

export async function clearHistory(database: string): Promise<void> {
  const res = await fetch(`/api/history?database=${encodeURIComponent(database)}`, {
    method: "DELETE",
    headers: ownerHeaders(),
  });
  if (!res.ok) throw await errorFrom(res);
}

/** Let anyone with the link see a saved answer. */
export function shareAnswer(id: string, shared = true): Promise<{ shared: boolean }> {
  return postJson(`/api/history/${encodeURIComponent(id)}/share`, { shared });
}

export interface Feedback {
  answer_id?: string | null;
  database: string;
  question: string;
  sql: string;
  rating: 1 | -1;
  corrected_sql?: string;
  comment?: string;
  provider?: string;
  model?: string;
}

/** 👍/👎 on an answer, with the user's corrected SQL when they fixed it. */
export function sendFeedback(feedback: Feedback): Promise<{ id: string }> {
  return postJson("/api/feedback", feedback);
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
    for (const [name, value] of Object.entries(ownerHeaders())) xhr.setRequestHeader(name, value);
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
  const res = await fetch(`/api/databases/${encodeURIComponent(id)}`, {
    method: "DELETE",
    headers: ownerHeaders(),
  });
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
  provider: KeyProvider,
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

/** The models a provider offers this user (more with their own key). */
export async function fetchModels(provider: Provider, apiKey?: string): Promise<ModelsResponse> {
  const res = await fetch(`/api/models?provider=${encodeURIComponent(provider)}`, {
    headers: ownerHeaders(apiKey ? { [KEY_HEADER]: apiKey } : {}),
  });
  if (!res.ok) throw await errorFrom(res);
  return (await res.json()) as ModelsResponse;
}
