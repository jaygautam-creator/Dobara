# Plan — 24 Aug → 3 Sep 2026

Hard deadline **5 Sep**. Target ship **3 Sep**. Two days of buffer, deliberately unplanned.

## The gate that matters

> **By end of Day 6 (30 Aug) the numbers must exist.** `make eval` must produce
> `artifacts/summary.json` with all five arms and confidence intervals.
>
> If that gate is missed, **cut the entire frontend** and submit a CLI + notebook + README.
> An honest, well-measured result with no UI beats a beautiful UI with no result. The bar
> says "show measured money recovered" — it does not mention a dashboard.

## Days

| Day | Date | Deliverable | Done when |
|---|---|---|---|
| 0 | 24 Aug | Repo, specs, decisions locked | Docs committed, stack decided, Razorpay test keys obtained |
| 1 | 25 Aug | Simulator core | `sim/params.yaml` fully sourced; NPCI figures pinned; entities + SQLite schema; `make sim` runs |
| 2 | 26 Aug | Simulator validated + splits | Output reproduces published benchmarks (failure rate, recovery rate, revocation ratio); temporal + cold-start + regime-shift splits built; leakage test passes |
| 3 | 27 Aug | Recovery model | LightGBM + logistic baseline; isotonic calibration; Brier + reliability diagram; slice metrics |
| 4 | 28 Aug | Revocation hazard + bank health | Person-period hazard model calibrated; EWMA with adaptive decay + change-point flag |
| 5 | 29 Aug | Agent + compliance + audit | `decide()` pure and typed; declarative rule engine; `hypothesis` property test green; audit trail rendering |
| 6 | 30 Aug | **Batch harness — THE GATE** | All 5 arms × 30 seeds; paired CIs; sensitivity; break-even; `artifacts/summary.json` exists |
| 7 | 31 Aug | API + Razorpay test mode | FastAPI, SSE streaming, real test-mode subscription objects and webhooks |
| 8 | 1 Sep | Control Room + Evidence page | `/`, `/control-room`, `/evidence` built; comparison toggle working |
| 9 | 2 Sep | Polish, README, deploy, CI | Architecture diagram; README quoting `summary.json`; deployed to `bom1`; CI green |
| 10 | 3 Sep | Video + submit | Recorded, submitted |
| — | 4–5 Sep | Buffer | Untouched unless needed |

## Scope-cut order

Cut strictly in this order. Never cut out of order to save something later in the list.

1. LLM Hinglish nudge composer → static approved templates only
2. `/mandate` timeline page
3. Audit "ask why" natural-language box
4. Approval queue UI
5. Neon deploy → serve committed artifacts, local-only live runs
6. Razorpay test-mode live integration → faithful mock of the API contract
7. Bank-health change-point detection → plain EWMA (abstention then keyed on slice size only)
8. Cold-start split → temporal split only
9. `/audit` detail page → JSON download link
10. Entire frontend → CLI + notebook

## Never cut, under any circumstance

- Honest metrics with confidence intervals
- All five evaluation arms, including `aggressive_8x` and `oracle`
- The gross-vs-net-LTV money chart
- The compliance gate and its property test
- The audit trail including rejected alternatives
- The abstention / graceful-failure case
- The "what we deliberately did not build" section
- Sourced simulator parameters and the assumptions table

## Standing risks

| Risk | Mitigation |
|---|---|
| Simulator produces implausible outcomes | Day 2 is validation against published benchmarks, not building |
| Revocation hazard dominates and every arm says "stop" | Sensitivity analysis catches it; report it honestly if true — it is still a finding |
| Razorpay test mode needs business verification | Fall back to a faithful mock; costs ~5% of impact, budgeted |
| Frontend eats the schedule | Day 6 gate; cut list is pre-agreed |
| Numbers look too good | Treat as a bug. Check leakage first, then latent-state exposure. Razorpay's own paper reports 4–6%. |
