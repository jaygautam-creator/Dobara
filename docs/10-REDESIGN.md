# 10 — Frontend Redesign Specification

> Supersedes the *visual* portions of `docs/08-FRONTEND-SPEC.md`. Everything 08 says
> about **what data appears on which page** still holds. This document governs **how it
> looks, ranks, and moves**. Where they conflict on visuals, this file wins.

**Decision (2026-08-28, user):** full redesign, every route. `motion` + `shadcn/ui`
authorised as new dependencies.

---

## 0. The register

The thesis is *restraint*. The interface must embody it, not contradict it.

**Target register: a regulatory dossier rendered by an operations terminal.**
High information density, precise typography, monospace numerics, one accent used
sparingly, motion only where it carries meaning.

**Explicitly rejected:** the generic AI-dashboard look — purple/violet gradients, glowing
cards, glassmorphism, floating orbs, animated mesh backgrounds, emoji as iconography,
`shadow-2xl` on everything. A product whose entire argument is "stop being aggressive"
cannot look like every other aggressive AI demo. If a change makes the page look more
like a startup landing template, it is wrong.

**The test for any new visual element:** does it help a judge understand the argument
faster? If not, delete it.

---

## 1. What is actually wrong today

Established by review of the current tree, 2026-08-28. Fix these specifically; do not
"redesign" things not on this list without a reason you can state.

1. **No hierarchy.** Every surface on the site is the same object:
   `rounded-lg border border-border bg-surface-1 p-5`. Landing FactCards, StatTiles,
   Callouts, cycle cards, and Cards are visually interchangeable, so nothing reads as
   important.
2. **The headline number has no rank.** ₹66/mandate renders at `text-2xl` in a tile
   identical to "Notifications sent." It is the single most important fact in the repo.
3. **The landing page describes the thesis instead of showing it.** The most persuasive
   asset we own — 8 legally-mandated notifications hammering a customer versus Dobara's
   2 — exists only as a paragraph.
4. **The architecture diagram is README-only.** Judges look at the site.
5. **Motion is globally dead.** `isAnimationActive={false}` on every `Line`/`Scatter`
   (added to make headless screenshots deterministic — a correct fix for the wrong
   scope) means every chart hard-pops. See §5 for the resolution that keeps screenshots
   deterministic *and* gives humans motion.
6. **One typeface, one weight range.** Geist Sans for everything, including numbers,
   which should be monospace and are not.
7. **`/evidence` is a 492-line wall.** Twelve-plus major sections, no in-page navigation,
   no progress, no way to find "the honesty panel" without scrolling blind.
8. **`/mandate/[id]` and `/audit/[id]` are unstyled data dumps.** The cycle cards are
   `w-40` boxes with a border; the audit page is a bare vertical stack of DecisionCards.
9. **The compliance gate — the structural centrepiece of the whole submission — has no
   visual representation anywhere.**

---

## 2. Hard constraints — a redesign that breaks any of these is a regression

- **`output: "export"`.** Static export, no server runtime at request time. No API
  routes, no server actions, no runtime data fetching. All data is pre-baked JSON read
  at build time through `lib/server-data.ts`. ~306 static pages must still build.
- **Every number keeps its CI and its source.** CLAUDE.md non-negotiable. A redesign may
  not drop a `ciText` or a `source` caption to make a tile look cleaner. If a number
  does not fit with its CI, the layout is wrong, not the CI.
- **No hand-typed numbers.** Every figure reads from `artifacts/*.json`. Never inline a
  literal like `66` in JSX.
- **Both themes, always.** Light and dark are both first-class (`:root`,
  `prefers-color-scheme`, `[data-theme]`). Never define a colour only inside a media
  query or only in one theme block.
- **`prefers-reduced-motion` is honoured everywhere.** Every animation added under §5
  must be fully disabled — not merely shortened — under reduced motion.
- **Headless screenshot determinism is preserved.** See §5.
- **`make check` and the web build (`tsc`, `eslint`, `next build`) stay green at the end
  of every session.** The deploy must never be left broken between sessions.
- **Palette discipline holds.** Arm colours stay locked to their `references/palette.md`
  slots; status colours are reserved and never reused as a series colour.

---

## 3. Foundations

### 3.1 Type

Three faces, each with one job. Load via `next/font/google`, subset latin, with real
fallback stacks.

| Role | Face | Used for |
|---|---|---|
| Editorial | **Instrument Serif** (or `Newsreader` if Instrument reads too tight) | Page titles, the thesis, pull-quotes. The "dossier" voice. |
| UI | **Geist Sans** (already loaded) | Labels, nav, body copy, table text. |
| Numeric | **Geist Mono** (already loaded, currently unused) | *Every* number on the site: stat values, CIs, table cells, axis ticks, timestamps, IDs, rupee amounts. |

**Rule: no number renders in a proportional face anywhere.** `tabular-nums` on Geist Mono.

Fluid scale, defined once in `globals.css` as custom properties and consumed by
Tailwind v4 `@theme`:

```
--step--1: clamp(0.75rem, 0.73rem + 0.10vw, 0.8125rem);
--step-0:  clamp(0.875rem, 0.85rem + 0.12vw, 0.9375rem);
--step-1:  clamp(1rem, 0.96rem + 0.2vw, 1.125rem);
--step-2:  clamp(1.25rem, 1.18rem + 0.35vw, 1.5rem);
--step-3:  clamp(1.625rem, 1.5rem + 0.6vw, 2rem);
--step-4:  clamp(2rem, 1.8rem + 1vw, 2.75rem);
--step-5:  clamp(2.5rem, 2.1rem + 2vw, 4rem);
--step-6:  clamp(3.25rem, 2.5rem + 3.6vw, 6rem);   /* hero metric only */
```

### 3.2 Surfaces and elevation

Replace the single flat card with four named treatments. Add them as component variants,
not ad-hoc class strings.

| Treatment | Look | Use |
|---|---|---|
| `plain` | no border, no background | grouping only |
| `inset` | `bg-surface-0`, inner hairline | a well *inside* a card (code blocks, sub-tables) |
| `raised` | `bg-surface-1`, `border-border`, hairline top highlight in dark | the default card |
| `feature` | `bg-surface-1`, 1px accent-tinted border, accent glow at 4% opacity | **exactly one per page** — the page's focal claim |

`feature` is rationed. Two on a page means neither is the focus.

### 3.3 Density tiers

`StatTile` gains a `size` prop:

- `hero` — value at `--step-6` in Geist Mono, label above in `--step--1` uppercase
  tracked, CI and source below. One per page maximum.
- `default` — current size, the grid workhorse.
- `compact` — for six-across counter rows; value at `--step-2`.

### 3.4 Spacing rhythm

Sections separate by a single scale: `space-y-24` between major page sections,
`space-y-8` within a section, `gap-4` inside grids. The current mix of `gap-14`,
`space-y-16`, `space-y-8`, `gap-6` is arbitrary — unify it.

### 3.5 Component library

Install `shadcn/ui` (Tailwind v4, React 19, `new-york` style, CSS-variable theming
pointed at the **existing** tokens in `globals.css` — do not let shadcn's init overwrite
the palette). Adopt only these primitives, replacing hand-rolled equivalents:

`tabs`, `tooltip`, `dialog`, `scroll-area`, `separator`, `table`, `badge`, `button`,
`accordion`, `hover-card`, `command` (for the mandate jump-to search).

Keep `StatTile`, `Callout`, `ArmSwatch`, `SectionHeading` hand-rolled in `ui.tsx` — they
encode project-specific rules (the CI requirement, the arm palette) that a generic
primitive would erode.

---

## 4. Route-by-route intent

### `/` — Thesis
Rebuild as an editorial argument in five beats.

1. **Hero.** Editorial serif, oversized. The claim and the motto. One accent line.
2. **The demonstration (the centrepiece — build this first, it is the highest-value
   single element on the site).** A scroll-triggered, side-by-side reconstruction of one
   failing mandate: the aggressive lane fires 8 pre-debit notifications in sequence, each
   one a discrete beat, ending in a revocation event that greys the whole lane out and
   stamps the forgone LTV. The Dobara lane fires 2, stops, and keeps the mandate alive
   with its remaining LTV intact. Numbers driven from real fixture data, not invented.
   Honours reduced-motion by rendering the completed end-state immediately.
3. **The three sourced facts** (20M / 24h / 8x) — keep the content, restyle as an
   editorial band rather than three identical cards.
4. **The equation.** `E[net | action]` as a typeset display object with each term
   annotated on hover/tap — not a `<pre>` block.
5. **Entry points** to Control Room, Evidence, Architecture.

### `/architecture` — NEW
The system diagram as a first-class page, not a README image.

- Interactive SVG: click or focus a node → a side panel explains that module, names its
  source file, and links to it on GitHub.
- **Draw the LLM boundary as a literal wall.** The single most distinctive architectural
  claim in this repo is that money decisions cannot pass through an LLM. Show the
  tabular/calibrated path in the accent colour crossing the wall to the action, and the
  LLM path confined to the narrative side, unable to cross. This is the diagram a judge
  will remember.
- Below it: the compliance gate as a sequence — candidate actions entering, HARD rules
  blocking, what survives.
- Static-safe: pure SVG + React state, no runtime data.

### `/control-room` — Operations console
Keep the density; give it rank and a spine.

- Hero counter row: `net LTV` promoted to a `hero` StatTile; the rest `compact`.
- **"Attempts not made" is the thesis counter** — give it the `feature` treatment and a
  short caption saying why a *non*-action is the headline.
- Queue: shadcn `table` + `scroll-area`, sticky header, keyboard navigable (↑/↓ to move,
  Enter to open), `command` palette to jump to a mandate by ID.
- The streaming reveal is good — keep it, but drive it with `motion` and make it
  skippable (click anywhere → complete instantly). Never make a judge wait.
- The `aggressive_8x` comparison toggle currently swaps numbers silently. Animate the
  delta: numbers tween, and the deltas annotate themselves (`+2,140 notifications`,
  `+18 revocations`) in status colours.
- Add the **compliance gate panel** to the active case: the candidate set that was
  generated, which HARD rules eliminated which candidates, what survived to be scored.

### `/evidence` — The dossier
The content is strong; the navigation is absent.

- Two-column: sticky left rail with section index + scroll-spy + reading progress;
  content right at `max-w-[68ch]` for prose, full-bleed for charts.
- Section anchors and deep links (`/evidence#honesty`) must work.
- Headline section gets the page's one `feature` card and the `hero` stat.
- Charts: `motion`-driven draw-on-enter (§5), consistent axis/legend/tooltip styling
  extracted to a shared `chartTheme.ts` — the three chart components currently repeat it.
- The honesty panel keeps its prominence. **Do not soften or bury it in an accordion.**
  It is a credibility asset, not a disclaimer to hide.

### `/mandate/[id]` — Timeline
- Rebuild as a real horizontal timeline with a continuous time axis, not `w-40` boxes in
  a wrap container. Cycles as labelled bands; attempts as events on the axis.
- Each event's action type carries a consistent glyph + colour; the terminal action of
  each cycle is emphasised.
- Show the notification burden as a running count alongside, so the timeline visibly
  demonstrates restraint.

### `/audit/[id]` — Audit trail
- `DecisionCard` redesigned around the spec's `SAW / THOUGHT / ALT / GATE / DID / WHY`
  structure as a labelled, scannable grid rather than a stack of paragraphs.
- Rejected alternatives shown as a comparison — what each scored, why it lost.
- The rupee maths shown as a worked equation with real numbers substituted in.
- `AskWhyBox` keeps its per-entry provenance line (`narrated by provider/model`)
  visible — that honesty detail is a feature; do not hide it behind a hover.

---

## 5. Motion

Install `motion`. Rules:

- Motion must carry meaning: reveal order, causality, magnitude of change. Never
  decoration.
- Durations 150–400ms; easing `[0.2, 0, 0, 1]`. Nothing bounces.
- Scroll reveals fire once, never re-trigger on scroll-up.
- Numbers tween on change (comparison toggle, hero metric on first view).

**Resolving the screenshot-determinism conflict.** Do not simply re-enable Recharts
animation — the `isAnimationActive={false}` change exists because headless capture froze
mid-draw. Instead, gate it centrally:

```ts
// web/lib/motion.ts
export const staticRender =
  typeof window !== "undefined" &&
  (new URLSearchParams(window.location.search).has("static") ||
    window.matchMedia("(prefers-reduced-motion: reduce)").matches);
```

Charts use `isAnimationActive={!staticRender}`. Screenshot recipes append `?static=1`,
so captures stay deterministic and humans get motion. Update the screenshot recipe in
`PROGRESS.md` when this lands.

---

## 6. Accessibility

- Contrast: body text ≥ 4.5:1, large text ≥ 3:1, **in both themes**. Verify, don't assume.
- Every interactive element is keyboard reachable with a visible focus ring.
- Colour is never the only carrier of meaning — arms and action types need a glyph or
  label too.
- Charts have a text alternative or an accessible data table.
- All motion disabled under `prefers-reduced-motion`.

---

## 7. Sequencing

Six sessions. **The deploy is green at the end of every one.** No session may leave a
route half-migrated.

| # | Session | Ships |
|---|---|---|
| A | Bookkeeping close-out | `PROGRESS.md`, `docs/DECISIONS.md` current |
| B | Foundations | fonts, type scale, surface tiers, `motion` + shadcn installed, `ui.tsx` rebuilt, `chartTheme.ts`, `lib/motion.ts`. Existing routes keep working on the new primitives. |
| C | `/` rebuild + `/architecture` | the demonstration, the LLM-boundary diagram |
| D | `/control-room` | hierarchy, table, command palette, compliance gate panel |
| E | `/evidence` | sticky rail, scroll-spy, chart polish |
| F | `/mandate`, `/audit`, a11y + perf + deploy | timeline, audit grid, final pass |

Session B is load-bearing: get the foundations right and C–F are fast. Do not start C
before B is committed and green.
