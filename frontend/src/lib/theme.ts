/** Theme handling: dark is the designed default; light is fully designed too.
 *  Preference is persisted; "system" follows prefers-color-scheme. */

export type ThemeChoice = "dark" | "light";
const KEY = "ap-theme";

export function appliedTheme(): ThemeChoice {
  const el = document.documentElement;
  return el.dataset.theme === "light" ? "light" : "dark";
}

export function storedTheme(): ThemeChoice | null {
  return localStorage.getItem(KEY) === "light" || localStorage.getItem(KEY) === "dark"
    ? (localStorage.getItem(KEY) as ThemeChoice)
    : null;
}

export function applyTheme(theme: ThemeChoice) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem(KEY, theme);
}

export function toggleTheme(): ThemeChoice {
  const next = appliedTheme() === "dark" ? "light" : "dark";
  applyTheme(next);
  return next;
}

/** Called once before React mounts (also mirrored inline in index.html to
 *  avoid a theme flash on first paint). */
export function initTheme() {
  const stored = storedTheme();
  const system = window.matchMedia("(prefers-color-scheme: light)").matches
    ? "light"
    : "dark";
  document.documentElement.dataset.theme = stored ?? system;
}
