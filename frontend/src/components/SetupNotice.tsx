import { KeyRound, Terminal } from "lucide-react";

import Doodle from "@/components/Doodle";
import { providerInfo } from "@/lib/providers";
import type { Provider } from "@/lib/types";

/** What to say when the chosen provider has no key yet. */
function keyHelp(provider: Provider): { title: string; body: React.ReactNode } | null {
  const { label, key } = providerInfo(provider);
  if (!key) return null;
  const name = label.replace(/ \(.*\)/, "");
  return {
    title: key.free ? `Add a free ${name} key to start` : `Add your ${name} key to use ${name}`,
    body: (
      <>
        {key.free ? "Get a free key" : "Create a key"} at{" "}
        <a
          href={key.url}
          target="_blank"
          rel="noreferrer"
          className="font-semibold text-accent-ink underline underline-offset-2"
        >
          {key.site}
        </a>{" "}
        and paste it here. It stays in your browser. Or pick another provider below.
      </>
    ),
  };
}

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
  const help = keyHelp(provider);
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
