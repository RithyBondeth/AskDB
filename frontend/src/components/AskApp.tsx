"use client";

import { ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import CommandPalette, { buildCommands } from "@/components/CommandPalette";
import Composer from "@/components/Composer";
import Examples from "@/components/Examples";
import Header from "@/components/Header";
import Sidebar, { SidebarDrawer } from "@/components/Sidebar";
import TurnView from "@/components/TurnView";
import { askStream, runSql } from "@/lib/stream";
import { getTheme, nextTheme, setTheme } from "@/lib/theme";
import type { AskError, HealthResponse, Provider, StreamEvent, Turn } from "@/lib/types";

const HISTORY_KEY = "askdb-history";
const HISTORY_MAX = 8;
const CONTEXT_TURNS = 3; // earlier answers sent with a follow-up

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
  const [turns, setTurns] = useState<Turn[]>([]);
  const [provider, setProvider] = useState<Provider>("claude");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [offline, setOffline] = useState(false);
  const [history, setHistory] = useState<string[]>([]);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  // Latest values for callbacks that outlive a render (stream handlers, shortcuts).
  const providerRef = useRef(provider);
  const turnsRef = useRef(turns);
  useEffect(() => {
    providerRef.current = provider;
    turnsRef.current = turns;
  }, [provider, turns]);

  const busy = turns.some((t) => t.status === "running");
  const lastDone = [...turns].reverse().find((t) => t.status === "done");

  const update = useCallback((id: string, fn: (t: Turn) => Turn) => {
    setTurns((ts) => ts.map((t) => (t.id === id ? fn(t) : t)));
  }, []);

  const remember = useCallback((q: string) => {
    setHistory((h) => {
      const next = [q, ...h.filter((x) => x !== q)].slice(0, HISTORY_MAX);
      saveHistory(next);
      return next;
    });
  }, []);

  const ask = useCallback(
    async (q: string) => {
      const trimmed = q.trim();
      if (!trimmed || turnsRef.current.some((t) => t.status === "running")) return;
      setQuestion("");
      remember(trimmed);

      const context = turnsRef.current
        .filter((t) => t.status === "done" && t.data)
        .slice(-CONTEXT_TURNS)
        .map((t) => ({ question: t.question, sql: t.data!.sql }));

      const id = crypto.randomUUID();
      const turn: Turn = {
        id,
        question: trimmed,
        provider: providerRef.current,
        status: "running",
        progress: { stage: "generate", attempt: 1, failures: [] },
        startedAt: Date.now(),
      };
      setTurns((ts) => [...ts, turn]);

      const controller = new AbortController();
      abortRef.current = controller;
      const onEvent = (e: StreamEvent) => {
        if (e.type === "stage") {
          update(id, (t) => ({
            ...t,
            progress: { ...t.progress, stage: e.stage, attempt: e.attempt ?? t.progress.attempt },
          }));
        } else if (e.type === "attempt_failed") {
          update(id, (t) => ({
            ...t,
            progress: {
              ...t.progress,
              stage: e.stage,
              failures: [
                ...t.progress.failures,
                { attempt: e.attempt, stage: e.stage, error: e.error },
              ],
            },
          }));
        }
      };

      try {
        const data = await askStream({
          question: trimmed,
          provider: turn.provider,
          context,
          onEvent,
          signal: controller.signal,
        });
        update(id, (t) => ({
          ...t,
          status: "done",
          data,
          seconds: (Date.now() - t.startedAt) / 1000,
          progress: { ...t.progress, stage: "present" },
        }));
      } catch (err) {
        const aborted = controller.signal.aborted;
        const error: AskError = aborted
          ? { message: "Stopped.", attempts: [] }
          : (err as AskError)?.message
            ? (err as AskError)
            : { message: "Something went wrong.", attempts: [] };
        update(id, (t) => ({
          ...t,
          status: "error",
          error,
          seconds: (Date.now() - t.startedAt) / 1000,
        }));
      } finally {
        if (abortRef.current === controller) abortRef.current = null;
      }
    },
    [remember, update],
  );

  const newChat = useCallback(() => {
    abortRef.current?.abort();
    setTurns([]);
    setQuestion("");
    inputRef.current?.focus();
  }, []);

  // Health check, then answer a shared ?q= link once.
  useEffect(() => {
    // localStorage is only available after mount.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setHistory(loadHistory());
    const shared = new URLSearchParams(window.location.search).get("q");
    fetch("/api/health")
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((h: HealthResponse) => {
        setHealth(h);
        setProvider(h.default_provider);
        providerRef.current = h.default_provider;
      })
      .catch(() => setOffline(true))
      .finally(() => {
        if (shared) {
          window.history.replaceState(null, "", window.location.pathname);
          ask(shared);
        }
      });
  }, [ask]);

  // Keyboard: ⌘K / Ctrl+K palette, "/" focuses the question box.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      } else if (
        e.key === "/" &&
        !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)
      ) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Bring the newest question to the top of the view so its answer has room to grow.
  useEffect(() => {
    if (!turns.length) return;
    const articles = endRef.current?.parentElement?.querySelectorAll("article");
    articles?.[articles.length - 1]?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [turns.length]);

  const insert = useCallback((text: string) => {
    setQuestion((q) => (q && !q.endsWith(" ") ? `${q} ${text}` : `${q}${text}`));
    setDrawerOpen(false);
    requestAnimationFrame(() => inputRef.current?.focus());
  }, []);

  const commands = useMemo(
    () =>
      // Builds closures only; refs inside `ask` are read when a command runs, not here.
      // eslint-disable-next-line react-hooks/refs
      buildCommands({
        history,
        ask,
        newChat,
        setProvider,
        cycleTheme: () => setTheme(nextTheme(getTheme())),
      }),
    [history, ask, newChat],
  );

  const sidebar = (
    <Sidebar
      history={history}
      onPick={ask}
      onClearHistory={() => {
        setHistory([]);
        saveHistory([]);
      }}
      onInsert={insert}
      disabled={busy}
    />
  );

  const composer = (
    <Composer
      inputRef={inputRef}
      value={question}
      onChange={setQuestion}
      onSubmit={() => ask(question)}
      onStop={() => abortRef.current?.abort()}
      provider={provider}
      onProviderChange={setProvider}
      models={health?.providers ?? null}
      busy={busy}
      followUpTo={lastDone?.question ?? null}
    />
  );

  return (
    <div className="page-backdrop flex min-h-screen flex-col">
      <Header
        health={health}
        offline={offline}
        hasThread={turns.length > 0}
        onNewChat={newChat}
        onOpenPalette={() => setPaletteOpen(true)}
        onOpenSchema={() => setDrawerOpen(true)}
      />

      <div className="mx-auto flex w-full max-w-7xl flex-1 gap-8 px-4">
        <main className="flex min-w-0 flex-1 flex-col">
          {turns.length === 0 ? (
            <div className="flex flex-1 flex-col justify-center gap-6 py-12">
              <div className="animate-fade-up text-center">
                <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-xs text-muted">
                  <span className="size-1.5 rounded-full bg-accent" />
                  Validated, read-only, self-correcting SQL
                </span>
                <h1 className="text-gradient mt-5 text-4xl font-semibold tracking-tight sm:text-6xl">
                  Ask your data anything.
                </h1>
                <p className="mx-auto mt-4 max-w-xl text-base text-muted">
                  Type a question in plain English. AskDB writes the SQL, checks it can’t change
                  anything, runs it, and fixes its own mistakes. Then keep the conversation going.
                </p>
              </div>
              <div className="mx-auto w-full max-w-3xl">{composer}</div>
              <div className="mx-auto w-full max-w-3xl">
                <Examples onPick={ask} disabled={busy} />
              </div>
            </div>
          ) : (
            <>
              <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-10 pt-8 pb-6">
                {turns.map((t, i) => (
                  <TurnView
                    key={t.id}
                    turn={t}
                    isLast={i === turns.length - 1}
                    busy={busy}
                    models={health?.providers ?? null}
                    onRunSql={async (sql) => {
                      try {
                        const res = await runSql(sql);
                        update(t.id, (cur) => ({
                          ...cur,
                          original: cur.original ?? cur.data,
                          data: {
                            ...res,
                            question: cur.question,
                            explanation: "You edited and ran this query.",
                          },
                        }));
                        return null;
                      } catch (err) {
                        return (err as AskError).message ?? "Query failed.";
                      }
                    }}
                    onRevert={() =>
                      update(t.id, (cur) => ({ ...cur, data: cur.original, original: undefined }))
                    }
                    onRetry={() => ask(t.question)}
                    onFollowUp={ask}
                    onShare={async () => {
                      const url = `${window.location.origin}/?q=${encodeURIComponent(t.question)}`;
                      try {
                        await navigator.clipboard.writeText(url);
                      } catch {
                        // clipboard blocked: nothing else to do
                      }
                    }}
                  />
                ))}
                <div ref={endRef} />
              </div>
              <div className="sticky bottom-0 z-20 bg-gradient-to-t from-background via-background/95 to-transparent pt-6 pb-4">
                <div className="mx-auto w-full max-w-4xl">
                  {composer}
                  <p className="mt-2 flex items-center justify-center gap-1.5 text-[11px] text-subtle">
                    <ShieldCheck className="size-3" />
                    Read-only: every query is validated and runs on a read-only connection.
                  </p>
                </div>
              </div>
            </>
          )}
        </main>

        <aside className="hidden w-80 shrink-0 lg:block">
          <div className="sticky top-20 py-8">{sidebar}</div>
        </aside>
      </div>

      <SidebarDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)}>
        {sidebar}
      </SidebarDrawer>

      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        commands={commands}
        onAsk={ask}
      />
    </div>
  );
}
