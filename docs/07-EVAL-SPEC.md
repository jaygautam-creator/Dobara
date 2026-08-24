# 07 — Evaluation Specification

> **This document describes the part of the project that actually wins the track.**
>
> The bar says *"show measured money recovered across a batch."* Everyone will produce a
> number. We produce **a number you can believe.**

## The five arms

All arms run over the identical held-out batch, identical seeds, identical simulator state.

| Arm | Policy | Why it is here |
|---|---|---|
| `do_nothing` | No recovery attempted | The floor. Establishes what is at stake. |
| `razorpay_default` | **Razorpay's documented production behaviour** — retry the following day; e-mandate retries only after the previous attempt confirms; bank-holiday shift T-1 / T-3; `pending` → `halted` | The honest baseline. Not a strawman we invented — theirs, cited. |
| `aggressive_8x` | The Western dunning playbook: up to 8 retries on a fixed escalating cadence | **The money arm.** Wins on gross recovery, loses on net LTV. This crossover is the pitch. |
| `dobara` | Our policy | — |
| `oracle` | Perfect foresight over latent state | The ceiling. Shows how much headroom remains and stops us overclaiming. |

## Metrics — reported per arm, all with 95% CI

| Metric | Note |
|---|---|
| **Gross ₹ recovered** | What everyone else reports |
| Recovery rate % | Of failed cycles |
| Attempts used | The cost driver |
| **Notifications sent** | Legally forced, one per attempt |
| **Revocations caused** | The hidden cost |
| **Net LTV delta** | `gross − revoked_LTV − channel_cost`. **The headline number.** |
| ₹ recovered per notification | Efficiency of customer attention |
| Human escalations | Load created for the merchant |
| Abstentions | Honesty of the confidence layer |

## Confidence intervals — non-negotiable

**30 seeds minimum.** Report seed-level variance plus bootstrap CI within seeds. Every
number in the README, the UI, and the video is written as:

> ₹4.2L recovered **[95% CI ₹3.8L – ₹4.6L]**, n=30 seeds

Not one bare point estimate anywhere. This alone will separate the submission from
essentially the entire field.

Paired comparisons between arms use the **same seeds** — report the paired difference and
its CI, not two independent intervals. If the CI on `dobara − razorpay_default` straddles
zero, **we say the result is not significant.** That sentence in a hackathon README is
worth more than a fabricated win.

## The money chart

A single figure. X-axis: time horizon in cycles. Two lines per arm:

- **Gross recovered** — `aggressive_8x` on top
- **Net LTV** — `aggressive_8x` crosses below `razorpay_default`, and below `dobara`

The crossover point is annotated. This is the twenty seconds the pitch video is built
around: *the obvious agent wins the month and loses the year.*

## Sensitivity analysis

Vary each assumption over its declared `sensitivity_range` and re-rank the arms:

- revocation hazard per failure notification
- LTV horizon / expected remaining cycles
- notification channel cost
- date-change offer response rate — **including 0%**, proving Tier 1 is not a dependency

**Then the honesty move that no one else will make:**

> ### Break-even reporting
> State the value of the revocation hazard **at which `aggressive_8x` would beat `dobara`**,
> and say whether the real-world value plausibly sits there.

Naming the condition under which you are wrong is the strongest credibility signal
available in a repo of this kind. Put it in the README under its own heading.

## Robustness slices

Reported separately, never hidden in the aggregate:

- Per bank — **including the regime-shift bank**, where `ABSTAIN` should fire
- Per method (UPI AutoPay / card / NACH / e-mandate)
- Per attempt index
- Cold-start mandates (unseen in training)
- During injected outage windows

## The permanent holdout arm

Dobara ships with a production feature, not just an evaluation trick: the agent
**always routes a configurable small percentage of failed debits to `razorpay_default`**,
so recovery lift stays continuously measurable after deployment.

This is what real growth teams do and no student will think of it. It says: *I have thought
about what happens after this ships, and I know you can never measure recovery unless you
deliberately do not attempt it on some.* One paragraph in the README; one toggle in the UI.

## Reproducibility

- `make eval` regenerates `artifacts/results.parquet` and `artifacts/summary.json`.
- **README and UI read numbers from those files.** Nothing is hand-typed. A CI check fails
  the build if a number in the README does not match `summary.json`.
- Seeds are explicit and recorded. Reruns are bit-for-bit identical.
- CI runs a reduced-seed eval on every push so the pipeline is proven live.

## The calibration expectation

Razorpay's own production routing paper reports a **4–6%** success-rate lift across
millions of real transactions. That is our credibility anchor.

> **If our headline lift looks enormous, we have a bug — and the README must say we checked.**

A modest, tightly-intervalled, well-sliced improvement is far more persuasive to a payments
engineer than a large one. Where we *should* look strong is not gross recovery but **net
LTV**, because that is the axis nobody else is optimising.
