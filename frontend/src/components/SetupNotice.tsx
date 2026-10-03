import { KeyRound, Terminal } from "lucide-react";

import Doodle from "@/components/Doodle";
import type { HealthResponse, Provider } from "@/lib/types";

const KEY_STEPS: Record<Provider, { title: string; steps: React.ReactNode[] }> = {
  free: {
    title: "Add a free model key to start",
    steps: [
      <>
        Get a free Gemini key at{" "}
        <a
          href="https://aistudio.google.com/apikey"
          target="_blank"
          rel="noreferrer"
          className="font-semibold text-accent-ink underline underline-offset-2"
        >
          aistudio.google.com/apikey
        </a>{" "}
        (no credit card).
      </>,
      <>
        Add <code className="font-mono text-[13px]">ASKDB_FREE_API_KEY=…</code> to{" "}
        <code className="font-mono text-[13px]">backend/.env</code>.
      </>,
      <>Restart the backend.</>,
    ],
  },
  claude: {
    title: "Add your Anthropic key to use Claude",
    steps: [
      <>
        Create a key at{" "}
        <a
          href="https://platform.claude.com/"
          target="_blank"
          rel="noreferrer"
          className="font-semibold text-accent-ink underline underline-offset-2"
        >
          platform.claude.com
        </a>
        .
      </>,
      <>
        Add <code className="font-mono text-[13px]">ANTHROPIC_API_KEY=…</code> to{" "}
        <code className="font-mono text-[13px]">backend/.env</code>.
      </>,
      <>Restart the backend, or switch to the Free model below.</>,
    ],
  },
  local: { title: "", steps: [] },
};

/** First-run help on the home screen: the backend is down, or the chosen model has no key. */
export default function SetupNotice({
  offline,
  health,
  provider,
}: {
  offline: boolean;
  health: HealthResponse | null;
  provider: Provider;
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
  if (!health || health.configured?.[provider] !== false) return null;
  const { title, steps } = KEY_STEPS[provider];
  if (!steps.length) return null;
  return (
    <Notice icon={KeyRound} title={title}>
      <ol className="list-decimal space-y-1 pl-5">
        {steps.map((s, i) => (
          <li key={i}>{s}</li>
        ))}
      </ol>
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
