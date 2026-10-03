import type { ReactNode } from "react";

// A small SQL tokenizer for display only: keywords, functions, strings,
// numbers, and comments. Good enough for generated SELECT queries.
const KEYWORDS = new Set(
  (
    "select from where join inner left right full outer cross on group by order having limit " +
    "offset as and or not in is null like between case when then else end distinct union all " +
    "intersect except with asc desc over partition exists cast recursive using natural"
  ).split(" "),
);

const TOKEN =
  /(--[^\n]*)|('(?:[^']|'')*')|("(?:[^"]|"")*")|(\b\d+(?:\.\d+)?\b)|([A-Za-z_][A-Za-z0-9_]*)(?=\s*\()|([A-Za-z_][A-Za-z0-9_]*)/g;

export function highlightSql(sql: string): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  let i = 0;
  for (const m of sql.matchAll(TOKEN)) {
    const start = m.index ?? 0;
    if (start > last) out.push(sql.slice(last, start));
    const [text, comment, str, quotedIdent, num, func, word] = m;
    let color: string | null = null;
    if (comment) color = "var(--syn-comment)";
    else if (str) color = "var(--syn-string)";
    else if (num) color = "var(--syn-number)";
    else if (func && !KEYWORDS.has(func.toLowerCase())) color = "var(--syn-func)";
    else if ((func || word) && KEYWORDS.has((func || word).toLowerCase()))
      color = "var(--syn-keyword)";
    else if (quotedIdent) color = null;
    out.push(
      color ? (
        <span
          key={i++}
          style={{ color }}
          className={color.includes("keyword") ? "font-medium" : ""}
        >
          {text}
        </span>
      ) : (
        text
      ),
    );
    last = start + text.length;
  }
  if (last < sql.length) out.push(sql.slice(last));
  return out;
}
