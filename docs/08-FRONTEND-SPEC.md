# 08 — Control Room (Frontend Specification)

A third of the submission is a five-minute video. The frontend is not decoration — it is
the medium through which the judges experience the decision layer. It must look like a
product a payments company would ship.

**Load the `dataviz` skill before writing any chart code.** The evidence page is the most
important screen in the video and must read as one designed system with correct error bars.

## Design direction

- **Dark, dense, precise.** Operations-console register, not marketing-site register.
- **Tabular numerals everywhere** for money. Money is right-aligned, always with ₹, always
  with the CI where one exists.
- Restrained accent use: one colour for recovered, one for at-risk, one for stopped. Never
  colour as decoration.
- **Never clone Razorpay's brand, logo, or colours.** Adjacent in seriousness, distinct in
  identity. Impersonation is a disqualifier.
- Theme-aware, responsive, accessible contrast.

## Routes

### `/` — The thesis
One screen that lands the argument before any UI appears.

- The hook: **20 million mandates revoked every month.**
- The mechanism: **every retry is legally required to carry its own 24-hour notification.**
- The conclusion: **every retry is a bet with downside.**
- The motto: *Recover the payment. Keep the mandate.*
- One CTA into the Control Room.

Every figure carries its source link inline. This page must be beautiful — it is the first
frame of the video and the first thing a judge sees on the deployed URL.

### `/control-room` — Live batch execution
The centrepiece.

- **Header counters**, live as the batch streams: ₹ at risk → ₹ recovered → **₹ net LTV**
  → notifications sent → revocations avoided → attempts *not* made.
  *"Attempts not made" as a headline metric is the whole thesis in one tile.*
- **Case queue**, ranked by ₹ at risk, streaming over SSE.
- **Decision cards** — for the active case, the audit block rendered visually: what it saw,
  the two calibrated probabilities with CIs, the rupee arithmetic laid out term by term,
  the rejected alternatives with their own E[net], and the compliance clauses lighting
  green one at a time.
- **The comparison toggle** — *"show what the aggressive agent would have done"*. Gross
  line rises, net LTV line falls. **This is the single most important interaction in the
  video.**
- **Approval queue** for actions above the sign-off threshold.
- **Abstention banner** when the agent declines to act, naming the reason.

### `/evidence` — The metrics
Where the track is won. Everything read from `artifacts/summary.json`.

- Five-arm comparison table, every cell with a 95% CI.
- **The money chart**: gross vs net LTV over the horizon, five arms, crossover annotated.
- Calibration: reliability diagrams for both models, Brier scores — **led with, before AUC.**
- PR curves and slice metrics, with the regime-shift bank broken out.
- Sensitivity tornado chart + **the break-even statement** rendered as a callout:
  *"aggressive retry would beat Dobara only if revocation hazard were below X — the
  observed range is Y."*
- The permanent-holdout explanation.
- An honesty panel: unsourced assumptions, test-set evaluation count, any result whose CI
  straddles zero stated plainly as not significant.

### `/audit/[decision_id]` — One decision, fully opened
The complete structured record, human-readable, with feature attribution, and a natural-
language **"ask why"** box backed by the LLM reading the structured trail (never inventing).

### `/mandate/[id]` — Timeline
Cycles, attempts, notifications, decisions, and the customer's declared preference if any —
on one horizontal timeline, so the *convergence* to a stable date is visible as a shape.

## Technical

- Next.js 15 App Router, TypeScript strict, Tailwind, shadcn/ui, Recharts.
- Types generated from the FastAPI OpenAPI schema — the contract is enforced, not assumed.
- SSE for the live run, with polling fallback.
- Deployed to Vercel, region `bom1`.
- **The deployed demo must work with no API key**, serving committed run artifacts.

## Scope-cut order for this page

If time runs short, cut in this order and no other: `/mandate` timeline → audit "ask why"
box → approval queue → `/audit` detail page. **`/evidence` and the comparison toggle are
never cut** — they are the submission.
