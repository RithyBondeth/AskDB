import SqlCard from "@/components/SqlCard";
import type { Attempt } from "@/lib/types";

// Shows each try: failed queries with the error fed back to the model, then
// the query that finally ran. This is the self-correction demo moment.
export default function AttemptsView({ attempts }: { attempts: Attempt[] }) {
  const succeeded = attempts.at(-1)?.error === null;
  return (
    <ol className="flex flex-col gap-3">
      {attempts.map((a, i) => (
        <li key={i} className="flex flex-col gap-2">
          <SqlCard
            sql={a.sql}
            label={
              a.error ? `Attempt ${i + 1} · failed at ${a.stage}` : `Attempt ${i + 1} · succeeded`
            }
          />
          {a.error && (
            <p className="rounded-md bg-danger-soft px-3 py-2 font-mono text-xs text-danger">
              {a.error}
              {i < attempts.length - 1 && (
                <span className="block pt-1 font-sans text-muted">
                  ↳ error sent back to the model to repair the query
                </span>
              )}
            </p>
          )}
        </li>
      ))}
      {succeeded && attempts.length > 1 && (
        <li className="text-sm text-success">
          Self-corrected after {attempts.length - 1} failed{" "}
          {attempts.length === 2 ? "attempt" : "attempts"}.
        </li>
      )}
    </ol>
  );
}
