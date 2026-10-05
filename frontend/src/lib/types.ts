// Mirrors the response models in backend/api/main.py.

export type Cell = string | number | boolean | null;
export type Provider = "claude" | "free" | "groq" | "openrouter" | "openai" | "local";
export type Stage = "generate" | "validate" | "execute" | "summarize";

export interface Attempt {
  sql: string;
  error: string | null;
  stage: "validate" | "execute" | null;
}

export type ChartType = "bar" | "line" | "pie" | "scatter";

export interface ChartSpec {
  type: ChartType | "none";
  x: string | null;
  y: string[] | null;
  reason: string;
  /** Long-format results: one series per value of this column (stacked bars, lines). */
  group?: string | null;
  /** Scatter: the column that names each point. */
  label?: string | null;
}

export interface AskResponse {
  question: string;
  provider: Provider | "manual";
  model: string;
  sql: string;
  explanation: string;
  columns: string[];
  rows: Cell[][];
  truncated: boolean;
  chart: ChartSpec;
  attempts: Attempt[];
  /** A plain-language answer. While streaming it arrives after the result. */
  summary?: string | null;
  /** The saved answer's id (share links, feedback), when the server keeps history. */
  id?: string | null;
}

export interface AskError {
  message: string;
  attempts: Attempt[];
}

export interface SchemaColumn {
  name: string;
  type: string;
  primary_key?: boolean;
}

export interface SchemaTable {
  name: string;
  columns: SchemaColumn[];
}

export interface SchemaResponse {
  dialect: string;
  tables: SchemaTable[];
  suggestions: string[];
}

export interface DatabaseInfo {
  id: string;
  name: string;
  kind: "sample" | "sqlite" | "csv" | "postgres" | "mysql";
  tables: number;
  size_bytes: number;
  created_at: string;
  /** Live connections: user@host:port/database (never the password). */
  detail?: string;
}

export interface DatabasesResponse {
  databases: DatabaseInfo[];
  allow_uploads: boolean;
  allow_connections?: boolean;
  max_upload_mb: number;
  save_history?: boolean;
}

/** GET /api/history: one saved answer in the list. */
export interface SavedAnswerSummary {
  id: string;
  database: string;
  question: string;
  created_at: string;
  shared: boolean;
  rating: 1 | -1 | null;
}

/** GET /api/history/{id}: a saved answer with its full response. */
export interface SavedAnswer {
  id: string;
  database: string;
  created_at: string;
  shared: boolean;
  rating: 1 | -1 | null;
  response: AskResponse;
}

/** POST /api/rows: another page of an answer's rows. */
export interface RowsPage {
  columns: string[];
  rows: Cell[][];
  truncated: boolean;
}

export interface HealthResponse {
  status: string;
  dialect: string;
  tables: number;
  default_provider: Provider;
  providers: Record<Provider, string>;
  /** Whether each provider has its key configured on the server. */
  configured: Record<Provider, boolean>;
}

/** Events from POST /api/ask/stream. */
export type StreamEvent =
  | { type: "stage"; stage: Stage; attempt?: number }
  | { type: "generated"; attempt: number; sql: string }
  | {
      type: "attempt_failed";
      attempt: number;
      stage: "validate" | "execute";
      error: string;
      sql: string;
      will_retry: boolean;
    }
  | { type: "result"; data: AskResponse }
  | { type: "summary"; text: string }
  | { type: "error"; status: number; detail: AskError };

/** Live progress of one question, built from stream events. */
export interface Progress {
  stage: Stage | "present" | null;
  attempt: number;
  failures: { attempt: number; stage: string; error: string }[];
}

/** One question and its answer in the conversation. */
export interface Turn {
  id: string;
  question: string;
  provider: Provider;
  /** The model asked (undefined: the provider's default). */
  model?: string;
  database: string;
  status: "running" | "done" | "error";
  progress: Progress;
  startedAt: number;
  seconds?: number;
  data?: AskResponse;
  original?: AskResponse; // the model's answer, kept when the user edits the SQL
  error?: AskError;
  /** The result is in and the plain-language summary is still being written. */
  summarizing?: boolean;
  /** The user's 👍/👎 on this answer. */
  rating?: 1 | -1;
  /** Opened from history or a share link rather than asked just now. */
  saved?: boolean;
}

/** GET /api/models: what the model menu offers for one provider. */
export interface ModelsResponse {
  provider: Provider;
  default: string;
  models: {
    id: string;
    label: string;
    note?: string;
    /** From the server's eval results, e.g. "89% on eval". */
    score?: string;
    accuracy?: number;
    /** The most accurate measured model of this provider. */
    recommended?: boolean;
  }[];
  /** live: from the provider for your key; allowed: the server's list; catalog: AskDB's list. */
  source: "live" | "allowed" | "catalog";
  error: string | null;
}
