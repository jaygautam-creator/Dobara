// Resolves the screenshot-determinism conflict from docs/10-REDESIGN.md §5: Recharts'
// mount animation froze mid-draw under headless capture (root-caused 2026-08-27, see
// docs/DECISIONS.md), so every chart shipped with isAnimationActive={false} -- correct
// for the screenshot pass, wrong for a human visitor, who then never sees any chart
// motion. `staticRender` lets a screenshot recipe opt back into the frozen, deterministic
// render (`?static=1`) while every other visitor -- including anyone with
// prefers-reduced-motion set -- gets the appropriate treatment by default.
export const staticRender =
  typeof window !== "undefined" &&
  (new URLSearchParams(window.location.search).has("static") ||
    window.matchMedia("(prefers-reduced-motion: reduce)").matches);
