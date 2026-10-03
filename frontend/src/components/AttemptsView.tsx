import { CircleCheck, CircleX, CornerDownRight } from "lucide-react";

import SqlCard from "@/components/SqlCard";
import type { Attempt } from "@/lib/types";

// Each try, the error fed back to the model, and the query that finally ran:
// the self-correction demo moment.
export default function AttemptsView({ attempts }: { attempts: Attempt[] }) {
  return (
    <ol className="relative flex flex-col gap-4">
      {attempts.map((a, i) => {
        const failed = a.error !== null;
        const Icon = failed ? CircleX : CircleCheck;
        return (
          <li key={i} className="relative pl-9">
            {i < attempts.length - 1 && (
              <span className="absolute top-7 bottom-[-1rem] left-[11px] w-px bg-border" />
            )}
            <Icon
              className={`absolute top-0.5 left-0 size-6 rounded-full bg-surface p-0.5 ${
                failed ? "text-danger" : "text-success"
              }`}
            />
            <p className="mb-2 text-sm font-medium">
              Attempt {i + 1}{" "}
              <span className="font-normal text-muted">
                {failed ? `· failed at ${a.stage}` : "· succeeded"}
              </span>
            </p>
            <SqlCard
              sql={a.sql}
              label={failed ? "Rejected query" : "Final query"}
              tone={failed ? "failed" : "success"}
            />
            {failed && (
              <div className="mt-2 rounded-lg bg-danger-soft px-3 py-2 text-xs">
                <p className="font-mono text-danger">{a.error}</p>
                {i < attempts.length - 1 && (
                  <p className="mt-1 flex items-center gap-1 text-muted">
                    <CornerDownRight className="size-3" />
                    Error sent back to the model to repair the query
                  </p>
                )}
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}
