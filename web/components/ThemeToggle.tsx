"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "dobara-theme";

/** Keeps the render's default (dark, matching the brand) unless a viewer has already
 * chosen otherwise -- this must match the inline script in layout.tsx exactly, since
 * that script sets the attribute before hydration to avoid a flash of the wrong theme. */
function readStoredTheme(): "light" | "dark" {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored === "light" ? "light" : "dark";
  } catch {
    return "dark";
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
