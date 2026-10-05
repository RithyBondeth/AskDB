"use client";

import { Check, Eye, EyeOff, KeyRound, Loader2, ShieldCheck, X } from "lucide-react";
import { useState } from "react";

import { type ApiKeys, type KeyProvider, maskKey } from "@/lib/keys";
import { PROVIDERS } from "@/lib/providers";
import { checkKey } from "@/lib/stream";

// Every provider that takes a key, in menu order.
const FIELDS = PROVIDERS.flatMap(({ id, label, icon, blurb, key }) =>
  key && id !== "local"
    ? [
        {
          id: id as KeyProvider,
          label,
          icon,
          placeholder: key.placeholder,
          hint: (
            <>
              {blurb}. {key.free ? "Free key" : "Paid key"} from{" "}
              <a
                href={key.url}
                target="_blank"
                rel="noreferrer"
                className="font-semibold text-accent-ink underline underline-offset-2"
              >
                {key.site}
              </a>
            </>
          ),
        },
      ]
    : [],
);

type Check = { state: "checking" } | { state: "done"; ok: boolean; message: string };

/** Lets each user bring their own model keys, kept in their browser. */
export default function KeysDialog({
  open,
  onClose,
  keys,
  onSave,
  serverKeys,
}: {
  open: boolean;
  onClose: () => void;
  keys: ApiKeys;
  onSave: (keys: ApiKeys) => void;
  /** Providers the server already has a key for (used when the user adds none). */
  serverKeys: Partial<Record<KeyProvider, boolean>>;
}) {
  if (!open) return null;
  // Remount the form each time it opens so drafts start from the saved keys.
  return <Form onClose={onClose} keys={keys} onSave={onSave} serverKeys={serverKeys} />;
}

function Form({
  onClose,
  keys,
  onSave,
  serverKeys,
}: {
  onClose: () => void;
  keys: ApiKeys;
  onSave: (keys: ApiKeys) => void;
  serverKeys: Partial<Record<KeyProvider, boolean>>;
}) {
  const [draft, setDraft] = useState<Record<KeyProvider, string>>(
    () =>
      Object.fromEntries(FIELDS.map(({ id }) => [id, keys[id] ?? ""])) as Record<
        KeyProvider,
        string
      >,
  );
  const [shown, setShown] = useState<Partial<Record<KeyProvider, boolean>>>({});
  const [checks, setChecks] = useState<Partial<Record<KeyProvider, Check>>>({});

  async function test(id: KeyProvider) {
    setChecks((c) => ({ ...c, [id]: { state: "checking" } }));
    const result = await checkKey(id, draft[id].trim());
    setChecks((c) => ({ ...c, [id]: { state: "done", ...result } }));
  }

  function save() {
    const next: ApiKeys = {};
    for (const { id } of FIELDS) if (draft[id].trim()) next[id] = draft[id].trim();
    onSave(next);
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-[8vh]"
      role="dialog"
      aria-modal="true"
      aria-label="API keys"
      onKeyDown={(e) => e.key === "Escape" && onClose()}
    >
      <button
        type="button"
        aria-label="Close"
        onClick={onClose}
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
      />
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save();
        }}
        className="card animate-pop-in relative max-h-[84vh] w-full max-w-lg overflow-y-auto p-5 shadow-2xl"
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="flex items-center gap-2 font-hand text-4xl leading-none font-bold">
              <KeyRound className="size-6" strokeWidth={2.5} />
              Your API keys
            </h2>
            <p className="mt-1 text-sm text-muted">
              AskDB uses your own key to talk to the model. You only need one, for the provider you
              pick under the question box. Your own key also unlocks every model that provider
              offers you.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="grid size-8 shrink-0 place-items-center rounded-md text-muted hover:bg-surface-2"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="mt-4 space-y-4">
          {FIELDS.map(({ id, label, icon: Icon, hint, placeholder }) => {
            const check = checks[id];
            const value = draft[id];
            return (
              <div key={id}>
                <label htmlFor={`key-${id}`} className="flex items-center gap-1.5 font-medium">
                  <Icon className="size-4" />
                  {label}
                  {keys[id] && (
                    <span className="ml-auto font-mono text-[11px] font-normal text-subtle">
                      saved {maskKey(keys[id])}
                    </span>
                  )}
                </label>
                <div className="mt-1.5 flex gap-2">
                  <div className="sketch-sm flex min-w-0 flex-1 items-center bg-surface">
                    <input
                      id={`key-${id}`}
                      type={shown[id] ? "text" : "password"}
                      value={value}
                      onChange={(e) => {
                        setDraft((d) => ({ ...d, [id]: e.target.value }));
                        setChecks((c) => ({ ...c, [id]: undefined }));
                      }}
                      placeholder={
                        serverKeys[id] && !value ? "Optional: the server has a key" : placeholder
                      }
                      autoComplete="off"
                      spellCheck={false}
                      className="min-w-0 flex-1 bg-transparent px-3 py-2 font-mono text-sm outline-none placeholder:font-sans placeholder:text-subtle"
                    />
                    <button
                      type="button"
                      onClick={() => setShown((s) => ({ ...s, [id]: !s[id] }))}
                      aria-label={shown[id] ? "Hide key" : "Show key"}
                      className="grid size-9 shrink-0 place-items-center text-muted hover:text-foreground"
                    >
                      {shown[id] ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                    </button>
                  </div>
                  <button
                    type="button"
                    onClick={() => test(id)}
                    disabled={!value.trim() || check?.state === "checking"}
                    className="btn-paper inline-flex items-center gap-1.5 px-3 text-sm font-medium disabled:opacity-50"
                  >
                    {check?.state === "checking" && <Loader2 className="size-3.5 animate-spin" />}
                    Test
                  </button>
                </div>
                <p className="mt-1 text-xs text-subtle">
                  {check?.state === "done" ? (
                    <span className={check.ok ? "text-success" : "text-danger"}>
                      {check.ok && <Check className="mr-1 inline size-3.5" strokeWidth={3} />}
                      {check.message}
                    </span>
                  ) : (
                    hint
                  )}
                </p>
              </div>
            );
          })}
        </div>

        <p className="mt-5 flex gap-2 rounded-lg bg-surface-2 p-3 text-xs text-muted">
          <ShieldCheck className="size-4 shrink-0 text-success" />
          Keys are saved only in this browser and sent with each question to the AskDB server, which
          uses them for that request and never stores them. Use a key you can revoke.
        </p>

        <div className="mt-4 flex items-center justify-end gap-2">
          <button type="button" onClick={onClose} className="btn-paper px-4 py-2 text-sm">
            Cancel
          </button>
          <button type="submit" className="btn-ink px-4 py-2 text-sm font-medium">
            Save keys
          </button>
        </div>
      </form>
    </div>
  );
}
