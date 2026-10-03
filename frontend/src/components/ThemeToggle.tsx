"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

import { getTheme, nextTheme, onThemeChange, setTheme, type Theme } from "@/lib/theme";

const ICONS = { system: Monitor, light: Sun, dark: Moon };

export default function ThemeToggle() {
  const [theme, setLocal] = useState<Theme>("system");

  useEffect(() => {
    // Sync with the theme the pre-paint script applied, and with the command palette.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLocal(getTheme());
    return onThemeChange(setLocal);
  }, []);

  const Icon = ICONS[theme];
  return (
    <button
      type="button"
      onClick={() => setTheme(nextTheme(theme))}
      title={`Theme: ${theme}`}
      aria-label={`Theme: ${theme}. Click to change.`}
      className="grid size-9 place-items-center rounded-lg border border-border bg-surface text-muted transition hover:text-foreground"
    >
      <Icon className="size-4" />
    </button>
  );
}
