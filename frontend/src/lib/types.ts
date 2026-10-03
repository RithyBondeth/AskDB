// Mirrors the response models in backend/api/main.py.

export type Cell = string | number | boolean | null;
export type Provider = "claude" | "free" | "local";
export type Stage = "generate" | "validate" | "execute";

export interface Attempt {
  sql: string;
  error: string | null;
  stage: "validate" | "execute" | null;
}

export interface ChartSpec {
  type: "bar" | "line" | "none";
  x: string | null;
  y: string[] | null;
  reason: string;
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
  kind: "sample" | "sqlite" | "csv";
  tables: number;
  size_bytes: number;
  created_at: string;
}

export interface DatabasesResponse {
  databases: DatabaseInfo[];
  allow_uploads: boolean;
  max_upload_mb: number;
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
  database: string;
  status: "running" | "done" | "error";
  progress: Progress;
  startedAt: number;
  seconds?: number;
  data?: AskResponse;
  original?: AskResponse; // the model's answer, kept when the user edits the SQL
  error?: AskError;
}
