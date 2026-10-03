import { KeyRound, Terminal } from "lucide-react";

import Doodle from "@/components/Doodle";
import type { Provider } from "@/lib/types";

const KEY_HELP: Partial<Record<Provider, { title: string; body: React.ReactNode }>> = {
  free: {
    title: "Add a free model key to start",
    body: (
      <>
        Get a free Google Gemini key at{" "}
        <a
          href="https://aistudio.google.com/apikey"
          target="_blank"
          rel="noreferrer"
          className="font-semibold text-accent-ink underline underline-offset-2"
        >
          aistudio.google.com/apikey
        </a>{" "}
        (no credit card), then paste it here. It stays in your browser.
      </>
    ),
  },
  claude: {
    title: "Add your Anthropic key to use Claude",
    body: (
      <>
        Create a key at{" "}
        <a
          href="https://platform.claude.com/"
          target="_blank"
          rel="noreferrer"
          className="font-semibold text-accent-ink underline underline-offset-2"
        >
          platform.claude.com
        </a>{" "}
        and paste it here, or switch to the Free model below.
      </>
    ),
  },
};

/** First-run help on the home screen: the backend is down, or the chosen model has no key. */
export default function SetupNotice({
  offline,
  configured,
  provider,
  onAddKey,
}: {
  offline: boolean;
  configured: Record<Provider, boolean> | null;
  provider: Provider;
  onAddKey: () => void;
}) {
  if (offline) {
    return (
      <Notice icon={Terminal} title="The backend isn’t running">
        <p>Start it in a second terminal, then reload this page:</p>
        <pre className="sketch-sm mt-2 overflow-x-auto bg-surface px-3 py-2 font-mono text-[13px]">
          cd backend && uv run uvicorn api.main:app --reload --port 8000
        </pre>
      </Notice>
    );
  }
  const help = KEY_HELP[provider];
  if (!help || configured?.[provider] !== false) return null;
  return (
    <Notice icon={KeyRound} title={help.title}>
      <p>{help.body}</p>
      <button
        type="button"
        onClick={onAddKey}
        className="btn-ink mt-3 inline-flex items-center gap-2 px-4 py-2 text-sm font-medium"
      >
        <KeyRound className="size-4" strokeWidth={2.5} />
        Add API key
      </button>
    </Notice>
  );
}

function Notice({
  icon: Icon,
  title,
  children,
}: {
  icon: typeof Terminal;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="animate-fade-up sketch flex items-center gap-4 bg-note-yellow p-4 shadow-[3px_3px_0_var(--ink)]">
      <Doodle name="laying" className="hidden w-28 shrink-0 sm:block" />
      <div className="min-w-0 text-[15px]">
        <p className="flex items-center gap-2 font-hand text-2xl leading-none font-bold">
          <Icon className="size-4.5" strokeWidth={2.5} />
          {title}
        </p>
        <div className="mt-2 text-foreground/85">{children}</div>
      </div>
    </div>
  );
}
