// Theme controller: light / dark / system. The choice is a UI preference (not a
// secret), so persisting it in localStorage is fine — unlike the bearer token,
// which stays memory-only. "system" removes the data-theme attribute so the
// prefers-color-scheme CSS in app.css applies.

export type ThemeChoice = "light" | "dark" | "system";

export const THEME_STORAGE_KEY = "raiker.theme";
const CHOICES: readonly ThemeChoice[] = ["light", "dark", "system"];

export function isThemeChoice(value: unknown): value is ThemeChoice {
  return typeof value === "string" && (CHOICES as readonly string[]).includes(value);
}

export function loadThemeChoice(): ThemeChoice {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isThemeChoice(stored) ? stored : "system";
  } catch {
    return "system";
  }
}

export function applyTheme(choice: ThemeChoice): void {
  const root = document.documentElement;
  if (choice === "system") {
    delete root.dataset.theme;
  } else {
    root.dataset.theme = choice;
  }
}

export function saveThemeChoice(choice: ThemeChoice): void {
  try {
    if (choice === "system") {
      window.localStorage.removeItem(THEME_STORAGE_KEY);
    } else {
      window.localStorage.setItem(THEME_STORAGE_KEY, choice);
    }
  } catch {
    // Storage unavailable (private mode): the theme still applies for this session.
  }
}

/** Resolve the theme actually rendered right now (system → media query). */
export function resolvedTheme(choice: ThemeChoice): "light" | "dark" {
  if (choice !== "system") return choice;
  try {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  } catch {
    return "light";
  }
}
