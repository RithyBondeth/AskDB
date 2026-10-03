// Mirrors the response models in backend/api/main.py.

export type Cell = string | number | boolean | null;

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

export type Provider = "claude" | "local";

export interface AskResponse {
  question: string;
  provider: Provider;
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

export interface SchemaTable {
  name: string;
  columns: { name: string; type: string }[];
}

export interface SchemaResponse {
  dialect: string;
  tables: SchemaTable[];
}

export interface HealthResponse {
  status: string;
  dialect: string;
  tables: number;
  default_provider: Provider;
  providers: Record<Provider, string>;
}
