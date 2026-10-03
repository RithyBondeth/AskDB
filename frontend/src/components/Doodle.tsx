import { DOODLES, type DoodleName } from "@/lib/doodles";

/** An Open Doodles illustration (CC0), drawn in the theme's ink and accent colors. */
export default function Doodle({
  name,
  className = "",
  title,
}: {
  name: DoodleName;
  className?: string;
  /** Leave empty for decorative use. */
  title?: string;
}) {
  const art = DOODLES[name];
  return (
    <svg
      viewBox={art.viewBox}
      className={`doodle ${className}`}
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      fillRule="evenodd"
    >
      {art.paths.map((p, i) => (
        <path key={i} className={p.tone === "ink" ? "doodle-ink" : "doodle-accent"} d={p.d} />
      ))}
    </svg>
  );
}
