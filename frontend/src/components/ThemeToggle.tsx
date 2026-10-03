"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

type Theme = "system" | "light" | "dark";
const ORDER: Theme[] = ["system", "light", "dark"];
const ICONS = { system: Monitor, light: Sun, dark: Moon };

export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("system");

  useEffect(() => {
    const t = document.documentElement.dataset.theme;
    // Sync with the theme the pre-paint script applied.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (t === "light" || t === "dark") setTheme(t);
  }, []);

  function cycle() {
    const next = ORDER[(ORDER.indexOf(theme) + 1) % ORDER.length];
    setTheme(next);
    const root = document.documentElement;
    if (next === "system") delete root.dataset.theme;
    else root.dataset.theme = next;
    try {
      if (next === "system") localStorage.removeItem("askdb-theme");
      else localStorage.setItem("askdb-theme", next);
    } catch {
      // storage unavailable: the choice just won't persist
    }
  }

  const Icon = ICONS[theme];
  return (
    <button
      type="button"
      onClick={cycle}
      title={`Theme: ${theme}`}
      aria-label={`Theme: ${theme}. Click to change.`}
      className="grid size-9 place-items-center rounded-lg border border-border bg-surface text-muted transition hover:text-foreground"
    >
      <Icon className="size-4" />
    </button>
  );
}
