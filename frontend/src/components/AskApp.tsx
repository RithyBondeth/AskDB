"use client";

import { useEffect, useState } from "react";

import Composer from "@/components/Composer";
import Examples from "@/components/Examples";
import Header from "@/components/Header";
import ResultView from "@/components/ResultView";
import Sidebar from "@/components/Sidebar";
import { ErrorView, LoadingView } from "@/components/StatusViews";
import type { AskError, AskResponse, HealthResponse, Provider } from "@/lib/types";

type State =
  | { status: "idle" }
  | { status: "loading"; question: string }
  | { status: "done"; data: AskResponse; seconds: number }
  | { status: "error"; question: string; error: AskError };

const HISTORY_KEY = "askdb-history";
const HISTORY_MAX = 8;

function loadHistory(): string[] {
  try {
    const raw = JSON.parse(localStorage.getItem(HISTORY_KEY) ?? "[]");
    return Array.isArray(raw) ? raw.filter((q) => typeof q === "string").slice(0, HISTORY_MAX) : [];
  } catch {
    return [];
  }
}

function saveHistory(items: string[]) {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(items));
  } catch {
    // storage unavailable: history just won't persist
  }
}

export default function AskApp() {
  const [question, setQuestion] = useState("");
  const [state, setState] = useState<State>({ status: "idle" });
  const [provider, setProvider] = useState<Provider>("claude");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [offline, setOffline] = useState(false);
  const [history, setHistory] = useState<string[]>([]);

  useEffect(() => {
    // localStorage is only available after mount.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setHistory(loadHistory());
    fetch("/api/health")
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((h: HealthResponse) => {
        setHealth(h);
        setProvider(h.default_provider);
      })
      .catch(() => setOffline(true));
  }, []);

  const busy = state.status === "loading";

  async function ask(q: string) {
    const trimmed = q.trim();
    if (!trimmed || busy) return;
    setQuestion(trimmed);
    setState({ status: "loading", question: trimmed });
    const next = [trimmed, ...history.filter((h) => h !== trimmed)].slice(0, HISTORY_MAX);
    setHistory(next);
    saveHistory(next);

    const started = performance.now();
    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question: trimmed, provider }),
      });
      const body = await res.json();
      if (res.ok) {
        setState({
          status: "done",
          data: body as AskResponse,
          seconds: (performance.now() - started) / 1000,
        });
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
    <div className="page-backdrop flex min-h-screen flex-col">
      <Header health={health} offline={offline} />

      <div className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-6 px-4 pt-8 pb-16 lg:flex-row lg:gap-8">
        <main className="flex min-w-0 flex-1 flex-col gap-6">
          {state.status === "idle" ? (
            <div className="animate-fade-up text-center sm:text-left">
              <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-xs text-muted">
                <span className="size-1.5 rounded-full bg-accent" />
                Validated, read-only, self-correcting SQL
              </span>
              <h1 className="text-gradient mt-4 text-4xl font-semibold tracking-tight sm:text-5xl">
                Ask your data anything.
              </h1>
              <p className="mt-3 max-w-2xl text-base text-muted">
                Type a question in plain English. AskDB writes the SQL, checks it can’t change
                anything, runs it, and fixes its own mistakes.
              </p>
            </div>
          ) : (
            <h1 className="text-gradient text-2xl font-semibold tracking-tight">
              Ask your data anything.
            </h1>
          )}

          <Composer
            value={question}
            onChange={setQuestion}
            onSubmit={() => ask(question)}
            provider={provider}
            onProviderChange={setProvider}
            models={health?.providers ?? null}
            busy={busy}
          />

          {state.status === "idle" && (
            <div className="flex flex-col gap-3">
              <p className="text-xs font-medium tracking-wide text-subtle uppercase">
                Try one of these
              </p>
              <Examples onPick={ask} disabled={busy} />
            </div>
          )}
          {state.status === "loading" && (
            <LoadingView key={state.question} question={state.question} provider={provider} />
          )}
          {state.status === "error" && <ErrorView question={state.question} error={state.error} />}
          {state.status === "done" && (
            <ResultView
              key={state.data.sql + state.seconds}
              data={state.data}
              seconds={state.seconds}
            />
          )}
        </main>

        <Sidebar
          history={history}
          onPick={ask}
          onClearHistory={() => {
            setHistory([]);
            saveHistory([]);
          }}
          disabled={busy}
        />
      </div>
    </div>
  );
}
