import { EXAMPLES } from "@/lib/examples";

export default function Examples({
  onPick,
  disabled,
}: {
  onPick: (q: string) => void;
  disabled: boolean;
}) {
  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {EXAMPLES.map(({ icon: Icon, text }, i) => (
        <button
          key={text}
          type="button"
          onClick={() => onPick(text)}
          disabled={disabled}
          style={{ animationDelay: `${i * 40}ms` }}
          className="animate-fade-up group flex items-center gap-3 rounded-xl border border-border bg-surface px-3.5 py-3 text-left text-sm text-muted transition hover:-translate-y-0.5 hover:border-accent/50 hover:text-foreground hover:shadow-md disabled:pointer-events-none disabled:opacity-50"
        >
          <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-accent-soft text-accent-ink transition group-hover:bg-accent group-hover:text-on-accent">
            <Icon className="size-4" />
          </span>
          {text}
        </button>
      ))}
    </div>
  );
}
