"use client";

import { useRef, type ReactNode } from "react";
import { useInView } from "motion/react";
import { useStaticRender } from "@/lib/motion";

/** Gates a chart's mount until it scrolls into view, so Recharts' own mount animation
 * becomes a scroll-triggered draw-on-enter (docs/10-REDESIGN.md §5: "reveal fires once,
 * never re-triggers on scroll-up") -- `once: true` means the observer never fires again
 * once satisfied, so scrolling back up cannot re-trigger it. A `?static=1` screenshot
 * pass (or prefers-reduced-motion) must never wait on scroll position at all -- it mounts
 * immediately, and `isAnimationActive={!isStatic}` on the chart itself then renders it
 * fully drawn rather than mid-animation. `minHeight` reserves the chart's real height so
 * nothing jumps when it mounts. */
export function ChartReveal({
  children,
  minHeight,
}: {
  children: ReactNode;
  minHeight: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const isStatic = useStaticRender();
  const inView = useInView(ref, { once: true, margin: "-80px 0px" });
  const shouldRender = isStatic || inView;

  return (
    <div ref={ref} style={{ minHeight: shouldRender ? undefined : minHeight }}>
      {shouldRender ? children : null}
    </div>
  );
}
