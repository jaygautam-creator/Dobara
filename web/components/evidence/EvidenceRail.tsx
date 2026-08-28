"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import { useStaticRender } from "@/lib/motion";

export type EvidenceSection = { id: string; label: string };

/** Sticky left-rail section index with scroll-spy (highlights the section currently in
 * view) and a reading-progress indicator -- docs/10-REDESIGN.md §4 `/evidence`: "sticky
 * left rail carrying a section index with scroll-spy and a reading-progress indicator."
 * Deep links (`/evidence#honesty`) work because the sections themselves are plain `id`s
 * on static-exported markup -- no server needed to resolve them, and this component only
 * adds the *active-state* highlighting on top of links that already work without JS. */
export function EvidenceRail({ sections }: { sections: EvidenceSection[] }) {
  const [activeId, setActiveId] = useState<string>(sections[0]?.id ?? "");
  const [progress, setProgress] = useState(0);
  const isStatic = useStaticRender();
  const visibleRatios = useRef<Map<string, number>>(new Map());

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          visibleRatios.current.set(entry.target.id, entry.isIntersecting ? entry.intersectionRatio : 0);
        }
        let bestId = activeId;
        let bestRatio = 0;
        for (const [id, ratio] of visibleRatios.current) {
          if (ratio > bestRatio) {
            bestRatio = ratio;
            bestId = id;
          }
        }
        if (bestRatio > 0) setActiveId(bestId);
      },
      { rootMargin: "-15% 0px -55% 0px", threshold: [0, 0.25, 0.5, 0.75, 1] },
    );
    for (const s of sections) {
      const el = document.getElementById(s.id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sections]);

  useEffect(() => {
    function onScroll() {
      const doc = document.documentElement;
      const scrollable = doc.scrollHeight - doc.clientHeight;
      setProgress(scrollable > 0 ? window.scrollY / scrollable : 0);
    }
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <nav
      aria-label="Evidence sections"
      className="sticky top-14 hidden h-fit max-h-[calc(100vh-4rem)] flex-col gap-4 self-start overflow-y-auto py-2 lg:flex"
    >
      <div className="h-0.5 w-full overflow-hidden rounded-full bg-surface-2">
        <motion.div
          className="h-full bg-arm-dobara"
          animate={{ width: `${progress * 100}%` }}
          transition={isStatic ? { duration: 0 } : { duration: 0.15, ease: [0.2, 0, 0, 1] }}
        />
      </div>
      <ul className="space-y-0.5 text-sm">
        {sections.map((s) => {
          const active = s.id === activeId;
          return (
            <li key={s.id}>
              <Link
                href={`#${s.id}`}
                aria-current={active ? "location" : undefined}
                className={`block rounded-md px-2.5 py-1.5 leading-snug transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-arm-dobara ${
                  active
                    ? "bg-surface-1 font-medium text-text-primary"
                    : "text-text-muted hover:bg-surface-1 hover:text-text-secondary"
                }`}
              >
                {s.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
