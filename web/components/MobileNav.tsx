"use client";

import { useState } from "react";
import Link from "next/link";

/** The desktop header nav (four links + theme toggle) overflows the viewport below
 * `lg` -- measured: document.scrollWidth 439px vs a 390/414px viewport, on every route,
 * because `nav` has no wrap and no mobile fallback. This is a mobile-only affordance
 * (a collapsed menu) sitting next to the same, unchanged desktop nav -- it renders
 * nothing at `lg` and up. */
export function MobileNav({ items }: { items: { href: string; label: string }[] }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="lg:hidden">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-label={open ? "Close menu" : "Open menu"}
        className="rounded-md px-2.5 py-1.5 text-text-secondary transition-colors hover:bg-surface-1 hover:text-text-primary"
      >
        {open ? "✕" : "☰"}
      </button>
      {open && (
        <nav className="absolute inset-x-0 top-full border-b border-border bg-surface-0 px-6 py-2 shadow-sm">
          {items.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setOpen(false)}
              className="block rounded-md px-3 py-2.5 text-sm text-text-secondary transition-colors hover:bg-surface-1 hover:text-text-primary"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      )}
    </div>
  );
}
