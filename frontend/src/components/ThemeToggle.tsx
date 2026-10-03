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
      className="btn-paper grid size-8 place-items-center text-foreground sm:size-9"
    >
      <Icon className="size-4" />
    </button>
  );
}
