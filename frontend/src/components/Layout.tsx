/** App shell: sidebar navigation + topbar. Domain-driven hierarchy.
 *  The public editorial layer lives at `/` (Landing); the console keeps
 *  dense instrument-panel chrome per ADR-009's two-layer split. */

import { Link, NavLink, Outlet } from "react-router-dom";
import { useQuery } from "../lib/useQuery";
import { ThemeToggle } from "./ThemeToggle";

const NAV = [
  { to: "/overview", label: "Overview", key: "M4 13h6V4H4v9Zm8 7h6v-9h-6v9ZM4 20h6v-4H4v4Zm8-11h6V4h-6v5Z" },
  { to: "/agents", label: "Agent Explorer", key: "M5 3h14v4H5V3Zm0 7h14v4H5v-4Zm0 7h14v4H5v-4Z" },
  { to: "/graph", label: "Trust Graph", key: "M6 6a2 2 0 1 1-.001 4.001A2 2 0 0 1 6 6Zm12 8a2 2 0 1 1-.001 4.001A2 2 0 0 1 18 14ZM6 14l6-4m0 8 6-4" },
  { to: "/delegations", label: "Delegation Center", key: "M4 6h10M4 12h16M4 18h12" },
  { to: "/security", label: "Security Center", key: "M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7l8-4Z" },
  { to: "/policies", label: "Policy Center", key: "M6 4h9l3 3v13H6V4Zm3 6h6M9 14h6" },
  { to: "/audit", label: "Audit Center", key: "M5 4h14v16H5V4Zm3 4h8M8 12h8M8 16h5" },
  { to: "/demo", label: "Killer Demo", key: "M13 3 4 14h6l-1 7 9-11h-6l1-7Z" },
];

export function Layout() {
  const { data: counts } = useQuery(async () => {
    const res = await fetch("/health");
    return res.ok ? { up: true } : { up: false };
  }, []);

  return (
    <div className="flex min-h-screen">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded focus:bg-(--color-accent) focus:px-3 focus:py-1 focus:text-(--color-bg)"
      >
        Skip to content
      </a>
      <aside
        className="flex w-56 shrink-0 flex-col border-r border-(--color-line-soft) bg-(--color-surface) max-md:fixed max-md:inset-y-0 max-md:z-40 max-md:hidden"
        aria-label="Primary"
      >
        <div className="flex items-center gap-2.5 px-4 py-4">
          <Link
            to="/"
            className="flex items-center gap-2.5 rounded-(--radius-sm)"
            aria-label="AgentPassport — back to home"
          >
            <span
              className="flex h-8 w-8 items-center justify-center rounded-(--radius-sm) border border-(--color-accent-dim) bg-(--color-accent-dim)/30"
              aria-hidden
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--color-accent)" strokeWidth="2">
                <path d="M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7l8-4Z" />
              </svg>
            </span>
            <span>
              <span className="block text-[13px] font-semibold tracking-tight">AgentPassport</span>
              <span className="block text-[10px] tracking-wide text-(--color-ink-faint) uppercase">
                trust infrastructure
              </span>
            </span>
          </Link>
        </div>
        <nav className="mt-1 flex-1 px-2" aria-label="Sections">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `mb-0.5 flex items-center gap-2.5 rounded-(--radius-sm) px-3 py-2 text-[13px] transition-colors duration-150 ease-out ${
                  isActive
                    ? "bg-(--color-surface-3) font-medium text-(--color-ink)"
                    : "text-(--color-ink-dim) hover:bg-(--color-surface-2) hover:text-(--color-ink)"
                }`
              }
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden>
                <path d={item.key} strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-(--color-line-soft) px-4 py-3">
          <span className="inline-flex items-center gap-1.5 text-[11px] text-(--color-ink-faint)">
            <span
              className={`h-1.5 w-1.5 rounded-full ${counts ? "bg-(--color-allow)" : "pulse-soft bg-(--color-condition)"}`}
              aria-hidden
            />
            {counts ? "API connected" : "connecting…"}
          </span>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-3 border-b border-(--color-line-soft) bg-(--color-surface) px-5 py-3 max-md:px-3">
          <p className="min-w-0 text-xs text-(--color-ink-faint)">
            demo environment · synthetic data ·{" "}
            <span className="mono">v1.0.0</span>
          </p>
          <div className="flex shrink-0 items-center gap-2.5">
            <nav className="flex gap-3 md:hidden" aria-label="Mobile">
              {NAV.map((item) => (
                <NavLink key={item.to} to={item.to} end={item.to === "/overview"} className="text-(--color-ink-dim)">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden>
                    <path d={item.key} strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </NavLink>
              ))}
            </nav>
            <ThemeToggle />
          </div>
        </header>
        <main id="main" className="min-w-0 flex-1 px-5 py-5 max-md:px-3">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
