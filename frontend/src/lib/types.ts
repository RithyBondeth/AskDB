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

export interface AskResponse {
  question: string;
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
