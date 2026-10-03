"use client";

import { useEffect, useState } from "react";

import AttemptsView from "@/components/AttemptsView";
import ResultChart from "@/components/ResultChart";
import ResultTable from "@/components/ResultTable";
import SchemaPanel from "@/components/SchemaPanel";
import SqlCard from "@/components/SqlCard";
import type { AskError, AskResponse, HealthResponse, Provider } from "@/lib/types";

const EXAMPLES = [
  "Which artist has the most albums?",
  "Total revenue by country, top 10",
  "Revenue per month in 2013",
  "Who are the top 5 customers by total spend?",
  "What was our revenue last quarter?",
];

type State =
  | { status: "idle" }
  | { status: "loading"; question: string }
  | { status: "done"; data: AskResponse }
  | { status: "error"; question: string; error: AskError };

export default function AskApp() {
  const [question, setQuestion] = useState("");
  const [state, setState] = useState<State>({ status: "idle" });
  const [provider, setProvider] = useState<Provider>("claude");
  const [models, setModels] = useState<Record<Provider, string> | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((h: HealthResponse) => {
        setModels(h.providers);
        setProvider(h.default_provider);
      })
      .catch(() => {});
  }, []);

  async function ask(q: string) {
    const trimmed = q.trim();
    if (!trimmed || state.status === "loading") return;
    setQuestion(trimmed);
    setState({ status: "loading", question: trimmed });
    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question: trimmed, provider }),
      });
      const body = await res.json();
      if (res.ok) {
        setState({ status: "done", data: body as AskResponse });
      } else {
        const detail = body?.detail;
        const error: AskError =
          detail && typeof detail === "object" && "message" in detail
            ? { message: detail.message, attempts: detail.attempts ?? [] }
            : { message: `Request failed (${res.status}).`, attempts: [] };
        setState({ status: "error", question: trimmed, error });
      }
    } catch {
      setState({
        status: "error",
        question: trimmed,
        error: { message: "Network error: could not reach the server.", attempts: [] },
      });
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-4 py-8 lg:flex-row">
      <main className="flex min-w-0 flex-1 flex-col gap-6">
        <header>
          <h1 className="text-2xl font-semibold tracking-tight">AskDB</h1>
          <p className="mt-1 text-sm text-muted">
            Ask a question in plain English. AskDB writes the SQL, checks it is read-only, runs it,
            and fixes its own mistakes.
          </p>
        </header>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            ask(question);
          }}
          className="flex flex-col gap-3"
        >
          <div className="flex gap-2">
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. Which genres sell the most tracks?"
              maxLength={1000}
              aria-label="Question"
              className="min-w-0 flex-1 rounded-lg border border-border bg-surface px-4 py-3 text-base outline-none focus:border-accent focus:ring-2 focus:ring-accent/30"
            />
            <button
              type="submit"
              disabled={state.status === "loading" || !question.trim()}
              className="rounded-lg bg-accent px-5 py-3 font-medium text-on-accent disabled:opacity-50"
            >
              {state.status === "loading" ? "Thinking…" : "Ask"}
            </button>
          </div>
          <ProviderToggle
            value={provider}
            onChange={setProvider}
            models={models}
            disabled={state.status === "loading"}
          />
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => ask(ex)}
                disabled={state.status === "loading"}
                className="rounded-full border border-border bg-surface px-3 py-1 text-sm text-muted hover:border-accent hover:text-foreground disabled:opacity-50"
              >
                {ex}
              </button>
            ))}
          </div>
        </form>

        {state.status === "loading" && (
          <div className="animate-pulse rounded-lg border border-border bg-surface p-6 text-sm text-muted">
            {provider === "local"
              ? "The open model is reasoning about the schema (this can take a while on a laptop)…"
              : "Reading the schema and writing SQL…"}{" "}
            <span className="text-foreground">“{state.question}”</span>
          </div>
        )}

        {state.status === "error" && (
          <section className="flex flex-col gap-4">
            <div className="rounded-lg border border-danger/40 bg-danger-soft p-4 text-sm">
              <p className="font-medium text-danger">Couldn’t answer that</p>
              <p className="mt-1">{state.error.message}</p>
            </div>
            {state.error.attempts.length > 0 && <AttemptsView attempts={state.error.attempts} />}
          </section>
        )}

        {state.status === "done" && <Result data={state.data} />}
      </main>

      <SchemaPanel />
    </div>
  );
}

function Result({ data }: { data: AskResponse }) {
  const corrected = data.attempts.length > 1;
  return (
    <section className="flex flex-col gap-4">
      <p className="text-xs text-muted">
        Answered by{" "}
        <span className="rounded bg-accent-soft px-1.5 py-0.5 font-mono text-foreground">
          {data.model}
        </span>
      </p>
      {corrected ? <AttemptsView attempts={data.attempts} /> : <SqlCard sql={data.sql} />}
      {data.explanation && <p className="text-sm text-muted">{data.explanation}</p>}
      {data.chart.type !== "none" && (
        <ResultChart columns={data.columns} rows={data.rows} chart={data.chart} />
      )}
      <ResultTable columns={data.columns} rows={data.rows} truncated={data.truncated} />
    </section>
  );
}

const PROVIDER_LABELS: Record<Provider, string> = {
  claude: "Claude",
  local: "Open model",
};

function ProviderToggle({
  value,
  onChange,
  models,
  disabled,
}: {
  value: Provider;
  onChange: (p: Provider) => void;
  models: Record<Provider, string> | null;
  disabled: boolean;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3 text-sm">
      <div
        role="radiogroup"
        aria-label="Model"
        className="inline-flex rounded-lg border border-border bg-surface p-0.5"
      >
        {(Object.keys(PROVIDER_LABELS) as Provider[]).map((p) => (
          <button
            key={p}
            type="button"
            role="radio"
            aria-checked={value === p}
            disabled={disabled}
            onClick={() => onChange(p)}
            className={`rounded-md px-3 py-1 disabled:opacity-50 ${
              value === p ? "bg-accent text-on-accent" : "text-muted hover:text-foreground"
            }`}
          >
            {PROVIDER_LABELS[p]}
          </button>
        ))}
      </div>
      {models && <span className="truncate font-mono text-xs text-muted">{models[value]}</span>}
    </div>
  );
}
