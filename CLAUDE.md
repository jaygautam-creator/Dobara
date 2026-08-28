# Dobara — Session Bootstrap

> **READ THIS FIRST, EVERY SESSION. Then read `PROGRESS.md`. Then start work.**

## What this is

**Dobara** (दोबारा, "again") — an AI revenue-recovery agent for Indian recurring
payments. Submission for the **Razorpay AI Buildathon, Track 03: AI Revenue Recovery**.
Solo build. Hard deadline **5 Sep 2026**; target ship **3 Sep 2026**.

Goal: get selected as a Razorpay AI Builder Intern. The repo, a 5-minute pitch
video, and the architecture are the entire application. There is no resume screen.

## The one-sentence thesis

> In India every payment retry is legally required to carry its own 24-hour
> pre-debit notification, so aggressive retrying is a mandated harassment machine
> that destroys 20 million UPI AutoPay mandates a month. Dobara treats each retry
> as a priced bet against mandate revocation and knows when to stop.

**Motto: "Recover the payment. Keep the mandate."**

## Session protocol — follow exactly

1. Read `PROGRESS.md`. The `## CURRENT STATE` block at the top is the truth.
2. Read the `docs/` spec for the phase you are working on (listed in PROGRESS.md).
3. Do the work. Small commits, conventional messages (`feat:`, `fix:`, `docs:`, `test:`).
4. Run `make check` before you finish (ruff + mypy + pytest).
5. **Before ending, update `PROGRESS.md`**: tick boxes, rewrite `## CURRENT STATE`,
   append anything learned to `docs/DECISIONS.md`.
6. Commit and push.

**Never re-litigate a decision recorded in `docs/DECISIONS.md` or `docs/03-TECH-STACK.md`.**
If you believe one is wrong, say so in one paragraph, then follow it anyway unless
the user overrules.

## Non-negotiables — violating any of these fails the submission

- **Defence-only, restraint-first.** Nothing in this repo may help anyone extract
  money more aggressively than is honest. When in doubt, the agent stops.
- **No individual cash-flow inference.** We never model a specific human's balance
  or income. Tiers 1–3 evidence only (see `docs/01-REGULATORY.md`). No probing debits.
- **Money decisions never pass through an LLM.** Tabular, calibrated, inspectable
  models only. LLMs are for narrative, language, and explanation. Enforced by
  architecture, not by prompt.
- **Every number reported must have a confidence interval and a stated source.**
  No bare point estimates anywhere in README, UI, or video.
- **Simulated data must be declared loudly.** Every simulator parameter carries a
  `source:` field. Un-sourced parameters are listed in the README as assumptions.
- **The compliance gate is structural.** An action that would breach RBI/TRAI/NPCI
  rules must be impossible to emit, not merely discouraged.
- **Audit everything.** Every decision logs: inputs seen, model outputs, action
  chosen, alternatives rejected and why, compliance clauses satisfied, rupee maths.

## Repo map

| Path | What |
|---|---|
| `PROGRESS.md` | **Living tracker. Source of truth for session handoff.** |
| `PLAN.md` | Day-by-day schedule and scope-cut order |
| `docs/00-THESIS.md` | Why this project wins; the insight; positioning |
| `docs/01-REGULATORY.md` | Legal research; compliance rules as executable spec |
| `docs/02-ARCHITECTURE.md` | System design, data flow, module contracts |
| `docs/03-TECH-STACK.md` | Every technology choice + why + what we rejected |
| `docs/04-DATA-MODEL.md` | Schemas + simulator specification |
| `docs/05-ML-SPEC.md` | Models, features, training, calibration |
| `docs/06-AGENT-SPEC.md` | Decision layer, action set, compliance gate, audit |
| `docs/07-EVAL-SPEC.md` | Batch harness, arms, CIs, sensitivity analysis |
| `docs/08-FRONTEND-SPEC.md` | Control Room design specification |
| `docs/09-DEMO-SCRIPT.md` | 5-minute pitch video plan |
| `docs/10-REDESIGN.md` | Frontend redesign spec — visual system, per-route intent, sequencing |
| `docs/DECISIONS.md` | Append-only log of decisions made during the build |

## Commands

```
make setup     # uv sync, install frontend deps
make sim       # regenerate simulated dataset
make train     # train + calibrate all models
make eval      # run the batch harness, all arms, write artifacts/
make api       # run FastAPI locally
make web       # run Next.js locally
make check     # ruff + mypy + pytest
make demo      # end-to-end: sim -> train -> eval -> api + web
```
