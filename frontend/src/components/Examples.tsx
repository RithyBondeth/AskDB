import { CalendarRange, ChartColumn, Crown, Globe, Hash, Sparkles, Trophy } from "lucide-react";

function iconFor(q: string) {
  const s = q.toLowerCase();
  if (/month|year|quarter|daily|per day/.test(s)) return CalendarRange;
  if (/^how many|\bcount\b/.test(s)) return Hash;
  if (/top|best|most/.test(s)) return /artist|album/.test(s) ? Crown : Trophy;
  if (/country|city|region/.test(s)) return Globe;
  if (/total|revenue|sum|by /.test(s)) return ChartColumn;
  return Sparkles;
}

export default function Examples({
  items,
  onPick,
  disabled,
}: {
  items: string[];
  onPick: (q: string) => void;
  disabled: boolean;
}) {
  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((text, i) => {
        const Icon = iconFor(text);
        return (
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
        );
      })}
    </div>
  );
}
