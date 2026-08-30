"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "dobara-theme";

/** Keeps the render's default (light, so a judge lands on the light site regardless of
 * OS setting -- docs/DECISIONS.md [2026-08-30]) unless a viewer has already chosen dark
 * -- this must match the inline script in layout.tsx exactly, since that script sets
 * the attribute before hydration to avoid a flash of the wrong theme. `?theme=` takes
 * the same precedence here as in that script, so the toggle's icon matches what's
 * actually on screen for a screenshot pass -- but it is never written to storage, so it
 * never overrides the viewer's own persisted choice on the next load. */
function readStoredTheme(): "light" | "dark" {
  try {
    const q = new URLSearchParams(window.location.search).get("theme");
    if (q === "light" || q === "dark") return q;
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<"light" | "dark" | null>(null);

  useEffect(() => {
    // One-time read of a browser-only API (localStorage) after mount, deliberately not
    // during render -- reading it during the initial render would return a different
    // value on the server (none) than the client, causing a hydration mismatch. This is
    // the documented exception to "don't setState synchronously in an effect": syncing
    // from an external, non-React source exactly once, not a derived-state anti-pattern.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTheme(readStoredTheme());
  }, []);

  function toggle() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.dataset.theme = next;
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // localStorage unavailable (private mode, blocked storage) -- the toggle still
      // works for this page load, it just won't persist across visits.
    }
  }

  // Render nothing meaningful until mounted, to avoid a hydration mismatch against
  // whatever the inline script already picked -- swap for the real button once we know.
  return (
    <button
      onClick={toggle}
      aria-label={theme === "light" ? "Switch to dark theme" : "Switch to light theme"}
      title={theme === "light" ? "Switch to dark theme" : "Switch to light theme"}
      className="rounded-md px-2.5 py-1.5 text-text-secondary transition-colors hover:bg-surface-1 hover:text-text-primary"
    >
      {theme === null ? null : theme === "dark" ? "☀︎" : "☾"}
    </button>
  );
}
