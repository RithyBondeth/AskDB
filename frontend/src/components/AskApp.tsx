"use client";

import { ShieldCheck, Upload } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import CommandPalette, { buildCommands } from "@/components/CommandPalette";
import Composer from "@/components/Composer";
import DatabasePicker from "@/components/DatabasePicker";
import Doodle from "@/components/Doodle";
import Examples from "@/components/Examples";
import Header from "@/components/Header";
import KeysDialog from "@/components/KeysDialog";
import SetupNotice from "@/components/SetupNotice";
import Sidebar, { SidebarDrawer } from "@/components/Sidebar";
import TurnView from "@/components/TurnView";
import UploadDialog from "@/components/UploadDialog";
import { type ApiKeys, keyFor, loadKeys, saveKeys } from "@/lib/keys";
import { askStream, deleteDatabase, runSql } from "@/lib/stream";
import { getTheme, nextTheme, setTheme } from "@/lib/theme";
import type {
  AskError,
  DatabaseInfo,
  DatabasesResponse,
  HealthResponse,
  Provider,
  SchemaResponse,
  StreamEvent,
  Turn,
} from "@/lib/types";

const HISTORY_KEY = "askdb-history";
const HISTORY_MAX = 8;
const CONTEXT_TURNS = 3; // earlier answers sent with a follow-up
const DATABASE_KEY = "askdb-database";
const SAMPLE = "sample";

// Recent questions are kept per database: a question only makes sense for its data.
function loadHistory(database: string): string[] {
  try {
    const raw = JSON.parse(localStorage.getItem(`${HISTORY_KEY}:${database}`) ?? "[]");
    return Array.isArray(raw) ? raw.filter((q) => typeof q === "string").slice(0, HISTORY_MAX) : [];
  } catch {
    return [];
  }
}

function saveHistory(database: string, items: string[]) {
  try {
    localStorage.setItem(`${HISTORY_KEY}:${database}`, JSON.stringify(items));
  } catch {
    // storage unavailable: history just won't persist
  }
}

function saveDatabase(id: string) {
  try {
    localStorage.setItem(DATABASE_KEY, id);
  } catch {
    // storage unavailable
  }
}

function loadDatabase(): string {
  try {
    return localStorage.getItem(DATABASE_KEY) ?? SAMPLE;
  } catch {
    return SAMPLE;
  }
}

export default function AskApp() {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [provider, setProvider] = useState<Provider>("free");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [offline, setOffline] = useState(false);
  const [history, setHistory] = useState<string[]>([]);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [keysOpen, setKeysOpen] = useState(false);
  const [keys, setKeys] = useState<ApiKeys>({});
  const [databases, setDatabases] = useState<DatabaseInfo[]>([]);
  const [uploads, setUploads] = useState({ allowed: false, maxMb: 50 });
  const [database, setDatabase] = useState<string>(SAMPLE);
  const [schema, setSchema] = useState<SchemaResponse | null>(null);
  const [schemaFailed, setSchemaFailed] = useState(false);

  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  // Latest values for callbacks that outlive a render (stream handlers, shortcuts).
  const providerRef = useRef(provider);
  const keysRef = useRef(keys);
  const turnsRef = useRef(turns);
  const databaseRef = useRef(database);
  useEffect(() => {
    providerRef.current = provider;
    keysRef.current = keys;
    turnsRef.current = turns;
    databaseRef.current = database;
  }, [provider, turns, database, keys]);

  // A provider is ready if the server has a key for it or the user added their own.
  const configured = useMemo(() => {
    if (!health?.configured) return null;
    const c = { ...health.configured };
    for (const p of ["free", "claude"] as const) c[p] = c[p] || Boolean(keys[p]);
    return c;
  }, [health, keys]);

  const busy = turns.some((t) => t.status === "running");
  const lastDone = [...turns].reverse().find((t) => t.status === "done");

  const update = useCallback((id: string, fn: (t: Turn) => Turn) => {
    setTurns((ts) => ts.map((t) => (t.id === id ? fn(t) : t)));
  }, []);

  const remember = useCallback((q: string) => {
    setHistory((h) => {
      const next = [q, ...h.filter((x) => x !== q)].slice(0, HISTORY_MAX);
      saveHistory(databaseRef.current, next);
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
        database: databaseRef.current,
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
          database: turn.database,
          context,
          apiKey: keyFor(keysRef.current, turn.provider),
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

  const refreshDatabases = useCallback(async (): Promise<DatabaseInfo[]> => {
    try {
      const res = await fetch("/api/databases");
      if (!res.ok) return [];
      const body = (await res.json()) as DatabasesResponse;
      setDatabases(body.databases);
      setUploads({ allowed: body.allow_uploads, maxMb: body.max_upload_mb });
      return body.databases;
    } catch {
      return [];
    }
  }, []);

  /** Switch database. A conversation belongs to one database, so this starts a new chat. */
  const selectDatabase = useCallback(
    (id: string) => {
      if (id !== databaseRef.current) newChat();
      databaseRef.current = id;
      setDatabase(id);
      saveDatabase(id);
    },
    [newChat],
  );

  // Schema, suggested questions, and recent questions for the selected database.
  useEffect(() => {
    let cancelled = false;
    // localStorage is only available after mount.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setHistory(loadHistory(database));
    setSchema(null);
    setSchemaFailed(false);
    fetch(`/api/schema?database=${encodeURIComponent(database)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((s: SchemaResponse) => !cancelled && setSchema(s))
      .catch((status) => {
        if (cancelled) return;
        if (status === 404 && database !== SAMPLE)
          selectDatabase(SAMPLE); // deleted elsewhere
        else setSchemaFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [database, selectDatabase]);

  // Startup, in order: pick the database (?db= link or last used), check health,
  // then answer a shared ?q= link. Asking earlier would race the database switch.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const shared = params.get("q");
    const initialDb = params.get("db") ?? loadDatabase();
    (async () => {
      // Keys live in localStorage, so they're read here rather than during render.
      const saved = loadKeys();
      setKeys(saved);
      keysRef.current = saved;
      const list = await refreshDatabases();
      if (list.some((d) => d.id === initialDb)) selectDatabase(initialDb);
      try {
        const res = await fetch("/api/health");
        if (!res.ok) throw new Error();
        const h = (await res.json()) as HealthResponse;
        setHealth(h);
        setProvider(h.default_provider);
        providerRef.current = h.default_provider;
      } catch {
        setOffline(true);
      }
      if (shared) {
        window.history.replaceState(null, "", window.location.pathname);
        ask(shared);
      }
    })();
  }, [ask, refreshDatabases, selectDatabase]);

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
        suggestions: schema?.suggestions ?? [],
        databases,
        currentDatabase: database,
        ask,
        newChat,
        setProvider,
        cycleTheme: () => setTheme(nextTheme(getTheme())),
        selectDatabase,
        upload: uploads.allowed ? () => setUploadOpen(true) : null,
        openKeys: () => setKeysOpen(true),
      }),
    [history, schema, databases, database, ask, newChat, selectDatabase, uploads.allowed],
  );

  const sidebar = (
    <Sidebar
      history={history}
      onPick={ask}
      onClearHistory={() => {
        setHistory([]);
        saveHistory(database, []);
      }}
      onInsert={insert}
      disabled={busy}
      schema={schema}
      schemaFailed={schemaFailed}
    />
  );

  const current = databases.find((d) => d.id === database);

  async function removeDatabase(db: DatabaseInfo) {
    if (!window.confirm(`Delete “${db.name}”? This removes the uploaded data from the server.`)) {
      return;
    }
    try {
      await deleteDatabase(db.id);
    } catch (e) {
      window.alert((e as AskError).message);
    }
    await refreshDatabases();
    if (db.id === databaseRef.current) selectDatabase(SAMPLE);
  }

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
      configured={configured}
      busy={busy}
      followUpTo={lastDone?.question ?? null}
      example={schema?.suggestions[0]}
    />
  );

  return (
    <div className="page-backdrop flex min-h-screen flex-col overflow-x-clip">
      <Header
        status={schema ? { dialect: schema.dialect, tables: schema.tables.length } : null}
        offline={offline}
        picker={
          <DatabasePicker
            databases={databases}
            current={current}
            onSelect={selectDatabase}
            onUpload={() => setUploadOpen(true)}
            onDelete={removeDatabase}
            allowUploads={uploads.allowed}
          />
        }
        hasThread={turns.length > 0}
        onNewChat={newChat}
        onOpenPalette={() => setPaletteOpen(true)}
        onOpenKeys={() => setKeysOpen(true)}
        needsKey={configured?.[provider] === false}
        onOpenSchema={() => setDrawerOpen(true)}
      />

      <div className="mx-auto flex w-full max-w-7xl flex-1 gap-8 px-4">
        <main className="flex min-w-0 flex-1 flex-col">
          {turns.length === 0 ? (
            <div className="flex flex-1 flex-col justify-center gap-8 py-10">
              <div className="animate-fade-up mx-auto grid w-full max-w-4xl items-center gap-6 md:grid-cols-[1.25fr_1fr]">
                <div className="text-center md:text-left">
                  <span className="sketch-sm inline-flex -rotate-1 items-center gap-2 bg-surface px-3 py-1 text-xs text-muted">
                    <ShieldCheck className="size-3.5 text-accent" strokeWidth={2.5} />
                    Validated · read-only · self-correcting SQL
                  </span>
                  <h1 className="mt-4 font-hand text-6xl leading-[0.95] font-bold sm:text-7xl">
                    Ask your data <span className="hl">anything.</span>
                  </h1>
                  <p className="mx-auto mt-4 max-w-md text-[17px] leading-relaxed text-muted md:mx-0">
                    Type a question in plain English. AskDB writes the SQL, checks it{" "}
                    <span className="squiggle text-accent">
                      <span className="text-foreground">can’t change anything</span>
                    </span>
                    , runs it, and fixes its own mistakes.
                  </p>
                </div>
                <Doodle
                  name="sittingReading"
                  className="mx-auto w-full max-w-[19rem] md:max-w-none"
                />
              </div>
              <div className="mx-auto flex w-full max-w-4xl flex-col gap-4">
                <SetupNotice
                  offline={offline}
                  configured={configured}
                  provider={provider}
                  onAddKey={() => setKeysOpen(true)}
                />
                {composer}
              </div>
              <div className="mx-auto flex w-full max-w-4xl flex-col gap-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-hand text-2xl leading-none font-bold">
                    Try asking{" "}
                    {current ? (
                      <span className="font-sans text-sm font-normal text-muted">
                        about {current.name}
                      </span>
                    ) : null}
                  </p>
                  {uploads.allowed && (
                    <button
                      type="button"
                      onClick={() => setUploadOpen(true)}
                      className="btn-paper inline-flex items-center gap-1.5 px-3 py-1.5 text-sm"
                    >
                      <Upload className="size-4" strokeWidth={2.25} />
                      Use your own data
                    </button>
                  )}
                </div>
                {schema ? (
                  <Examples items={schema.suggestions} onPick={ask} disabled={busy} />
                ) : (
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {[0, 1, 2].map((i) => (
                      <div key={i} className="skeleton h-16" />
                    ))}
                  </div>
                )}
              </div>
              <p className="text-center text-xs text-subtle">
                Illustrations by{" "}
                <a
                  href="https://www.opendoodles.com"
                  target="_blank"
                  rel="noreferrer"
                  className="underline decoration-dotted underline-offset-2 hover:text-foreground"
                >
                  Open Doodles
                </a>{" "}
                (Pablo Stanley, CC0)
              </p>
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
                        const res = await runSql(sql, t.database);
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
                    onEdit={() => {
                      setQuestion(t.question);
                      requestAnimationFrame(() => inputRef.current?.focus());
                    }}
                    onFollowUp={ask}
                    onShare={async () => {
                      const db =
                        t.database === SAMPLE ? "" : `&db=${encodeURIComponent(t.database)}`;
                      const url = `${window.location.origin}/?q=${encodeURIComponent(t.question)}${db}`;
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

      <UploadDialog
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        maxMb={uploads.maxMb}
        onUploaded={async (info) => {
          setUploadOpen(false);
          await refreshDatabases();
          selectDatabase(info.id);
        }}
      />

      <KeysDialog
        open={keysOpen}
        onClose={() => setKeysOpen(false)}
        keys={keys}
        serverKeys={health?.configured ?? {}}
        onSave={(next) => {
          setKeys(next);
          saveKeys(next);
          setKeysOpen(false);
        }}
      />

      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        commands={commands}
        onAsk={ask}
      />
    </div>
  );
}
