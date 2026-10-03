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

// Sticky-note colors and a slight, varied tilt.
const NOTES = ["bg-note-yellow", "bg-note-pink", "bg-note-mint", "bg-note-sky"];
const TILTS = [-1.2, 0.8, -0.6, 1.1, -0.9, 0.5];

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
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((text, i) => {
        const Icon = iconFor(text);
        return (
          <button
            key={text}
            type="button"
            onClick={() => onPick(text)}
            disabled={disabled}
            style={{ transform: `rotate(${TILTS[i % TILTS.length]}deg)` }}
            className={`note flex items-start gap-3 px-4 py-3.5 text-left text-[15px] leading-snug text-foreground disabled:pointer-events-none disabled:opacity-50 ${NOTES[i % NOTES.length]}`}
          >
            <Icon className="mt-0.5 size-4.5 shrink-0" strokeWidth={2.25} />
            {text}
          </button>
        );
      })}
    </div>
  );
}
