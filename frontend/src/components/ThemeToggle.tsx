import { useSyncExternalStore } from "react";
import { appliedTheme, toggleTheme, type ThemeChoice } from "../lib/theme";

function subscribeTheme(onChange: () => void) {
  // data-theme is mutated in place; observe the attribute + cross-tab sync
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme"],
  });
  window.addEventListener("storage", onChange);
  return () => {
    observer.disconnect();
    window.removeEventListener("storage", onChange);
  };
}

function useTheme(): ThemeChoice {
  return useSyncExternalStore(
    subscribeTheme,
    appliedTheme,
    () => "dark" as ThemeChoice,
  );
}

/** Accessible dark/light switch. Sun shown in dark mode (action: go light). */
export function ThemeToggle({ className = "" }: { className?: string }) {
  const theme = useTheme();
  const light = theme === "light";
  return (
    <button
      type="button"
      onClick={() => toggleTheme()}
      aria-label={light ? "Switch to dark theme" : "Switch to light theme"}
      aria-pressed={light}
      title={light ? "Switch to dark theme" : "Switch to light theme"}
      className={`inline-flex h-8 w-8 items-center justify-center rounded-(--radius-sm) border border-(--color-line-soft) text-(--color-ink-dim) transition-colors duration-(--duration-fast) hover:bg-(--color-surface-2) hover:text-(--color-ink) ${className}`}
    >
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden>
        {light ? (
          <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4 8.5 8.5 0 1 0 20 14.5Z" strokeLinecap="round" strokeLinejoin="round" />
        ) : (
          <>
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" strokeLinecap="round" />
          </>
        )}
      </svg>
    </button>
  );
}
