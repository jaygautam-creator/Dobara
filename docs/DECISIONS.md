# Decision Log

Append-only. Newest at the bottom. **Never re-litigate an entry here without the user
explicitly overruling it.** Every session that makes a non-obvious choice appends to this.

Format: `## [DATE] — decision` / **Chose:** / **Over:** / **Because:**

---

## [2026-08-24] Track selection
**Chose:** Track 03 — AI Revenue Recovery.
**Over:** Track 02 (AI Risk Manager), Track 04 (Finance Controller).
**Because:** Track 02 is the crowded lane and has an unfixable data-provenance hole
(no public dispute datasets; synthesised labels would undermine the "honest metrics" bar
it is judged on). Track 03's metric is rupees, which is legible in one sentence; its data
problem is anchorable to published NPCI/RBI figures; and payment recovery is Razorpay's
most-sold capability.

## [2026-08-24] Loss class
**Chose:** Failed recurring mandate debits in India (UPI AutoPay / e-mandate / NACH / card).
**Over:** Checkout abandonment, B2B receivables, the full range in the brief.
**Because:** The brief lists a *range*; picking one point is required. This one is
batch-native, rupee-denominated, and regulation-rich.

## [2026-08-24] Objective function
**Chose:** Maximise expected **net LTV**: `P(success)·amount − P(revoke)·LTV_remaining − cost`.
**Over:** Maximise gross recovery / recovery rate.
**Because:** >20M UPI AutoPay mandates are revoked monthly over low balance, and Indian
regulation forces a customer notification before *every* retry — so attempts are causally
linked to revocation. Optimising gross recovery is value-destructive in this market.

## [2026-08-24] Evidence ladder — Tier 4 refused
**Chose:** Use declared preference, our own interaction history, and cohort priors.
**Over:** Modelling an individual customer's balance or cash-flow.
**Because:** Surveillance, and unnecessary. Also aligns with DPDP data minimisation. The
refusal is documented publicly — declining a capability you could have built is a stronger
signal than the feature would have been. Probing debits likewise refused.

## [2026-08-24] Language — Python, not Rust
**Chose:** Python 3.12 backend/ML, TypeScript frontend.
**Over:** Rust.
**Because:** The judged artifact is decision quality and measurement rigour, not
throughput; we have no performance constraint; no mature Rust equivalent of
LightGBM + isotonic calibration; on a 10-day solo budget Rust costs ~40% of the time for
zero judged points and makes the repo harder for a judge to run. Documented in
`03-TECH-STACK.md` including where Rust *would* be correct.

## [2026-08-24] Hosting — Vercel, not Cloudflare
**Chose:** Vercel (Fluid Compute, region `bom1`).
**Over:** Cloudflare Workers.
**Because:** Cloudflare's Python runtime is Pyodide-based and cannot load native wheels —
`lightgbm`/`scipy` will not run. Vercel runs real CPython with native deps up to 5 GB.
Decisive on that single fact. `bom1` also gives a correct data-residency posture given
RBI's localisation directive.

## [2026-08-24] Database — SQLite primary
**Chose:** SQLite locally (committed as a reproducible artifact), Neon Postgres free tier
for the deployed demo, one SQLAlchemy schema.
**Over:** Postgres everywhere.
**Because:** `git clone && make demo` with zero infrastructure is worth more than any
hosted feature for a repo-judged submission.

## [2026-08-24] LLM boundary
**Chose:** LLM for narrative, Hinglish nudge composition inside approved templates, and
audit Q&A. **Never** for probability estimation or the money decision. Enforced by import
boundary and a test.
**Because:** Money decisions must be calibrated and inspectable. Stating the boundary
explicitly is itself the signal that "AI Builder" is understood correctly.

## [2026-08-24] Regulatory ambiguity — conservative reading
**Chose:** Treat every retry as requiring its own 24-hour pre-debit notification
(`config.retry_requires_fresh_pdn = true`), and flag the ambiguity openly in the README.
**Over:** The convenient reading that the original cycle notification covers retries.
**Because:** Sources agree retries need a PDN and that retries skipping it are rejected
outright, but the in-cycle case is not crisply settled publicly. Choosing the stricter
side and documenting it is the instinct a payments company wants.

## [2026-08-25] AutoPay volume figures — pinned 50M/808M, not "120M"
**Chose:** 50 million new UPI AutoPay mandate registrations/month and 808 million mandate
executions/month, both July 2025, sourced to NPCI data via Business Standard.
**Over:** "Over 120 million AutoPay mandates created every month," which recurs across
secondary fintech blog sources.
**Because:** The 120M figure is never traced to a specific NPCI release, its reference
month is unstated, and it is inconsistent about whether it counts new mandates, active
mandates, or monthly executions. The 50M/808M pair is dated, paired with a same-source
YoY comparison, and internally consistent. NPCI's own ecosystem-statistics page returns
403 to automated fetches and could not be cross-checked directly this session — flagged
in `docs/04-DATA-MODEL.md` rather than silently worked around.

## [2026-08-25] Simulator retry correlation — added, not in the original spec
**Chose:** same-cycle retries are correlated with the prior attempt's outcome via
`retry_policy.within_cycle_repeat_failure_correlation` (0.65, assumption, sensitivity range
declared), rather than each retry being an independent Bernoulli draw against the bank's
base TD/BD.
**Over:** i.i.d. per-attempt draws (the initial implementation).
**Because:** i.i.d. draws produced an 89.9% within-cycle recovery rate against a published
dunning-recovery benchmark of 30-45% avg / 55-70% top quartile — a real failure mode
(insufficient funds, a bank issue) mostly persists across a next-day retry rather than
resolving itself. Adding the correlation brought recovery to ~46% at seed 42, consistent
across seeds 0-2. This is exactly the kind of "numbers look too good, check the mechanism"
case `PLAN.md` warns about.

## [2026-08-25] `sim/params.yaml` — YAML 1.1 boolean-key gotcha
**Chose:** quote the `YES` bank id as `"YES"` in `sim/params.yaml`.
**Because:** PyYAML's default (YAML 1.1) parses the unquoted key `YES:` as the boolean
`True`, silently breaking `banks.YES.base_td` lookups. Caught by the reproducibility test
failing with `KeyError`. Worth remembering if more bank ids or config keys collide with
YAML 1.1's boolean words (`yes/no/true/false/on/off`).

## [2026-08-25] Calibration gate made real — mean-across-5-seeds pytest, CI-enforced
**Chose:** `sim/run.py`'s `BENCHMARKS` dict stays print-only for human eyeballing during
`make sim`, but `tests/test_calibration.py` now runs the default-scale simulation across
5 seeds and asserts the MEAN of each metric against the same bands. This runs in CI via
`make check` / `pytest`, so a calibration regression fails the build.
**Over:** leaving the benchmark check as a non-failing print (the Phase 1 state).
**Because:** a check nobody enforces is not a check. Per-seed variance is real (n=5000 is
not infinite), so the test asserts on the mean across seeds rather than each seed
individually, which would be flaky.

## [2026-08-25] Revocation hazard recalibrated to the revocations/execution target
**Chose:** raised `revocation.base_hazard_per_cycle` 0.006 -> 0.0175 and
`revocation.hazard_per_failure_notification` 0.031 -> 0.098, both re-sourced with widened
`sensitivity_range`s in `sim/params.yaml`.
**Over:** the original Day-1 values, calibrated only loosely against the >20M/month figure
without a precise denominator.
**Because:** a new, harder benchmark — `revocations / mandate_executions ~= 2.5%` (20M /
808M, both already pinned) — jointly constrains failure_rate and P(revoke | failure), the
exact product the thesis depends on. The original values produced ~1.1%, under-producing
revocations ~2.2x. That was the conservative direction (it understated the cost of
aggressive retrying) but still a miscalibration worth fixing rather than keeping as a
convenient bias. Verified across seeds 0-4: mean `revocation_per_execution_ratio` ~= 2.45%,
inside the declared [1.5%, 4%] band (caveats on the 2.5% target documented in
`docs/04-DATA-MODEL.md`).
**Side effect, not incidental:** this recalibration also pulled `recovery_rate` down from
~46% to ~41% (mandates now churn out of the retry sequence earlier), which let the
benchmark band tighten — see the next entry.

## [2026-08-25] `recovery_rate` benchmark band tightened to (0.28, 0.48)
**Chose:** tightened from the original Day-1 band (0.15, 0.75) — deliberately wide because
nothing had been calibrated against it yet — to (0.28, 0.48), close to the published 30-45%
average dunning recovery rate.
**Over:** leaving the wide band, or tightening all the way to (0.30, 0.45) with no margin.
**Because:** after the revocation recalibration above, the simulated mean landed at ~41%
across seeds 0-4 (range 40.9%-42.5%), comfortably inside the published average band. A
small margin below 30% and above 45% is kept for seed-to-seed variance rather than pinning
the band exactly to the literature range, which would make the test flaky rather than
meaningful. This band was reached without conflicting with the revocations/execution
target — both benchmarks pass simultaneously at the current calibration, so no further
loosening was necessary.

## [2026-08-25] Fixed: `Customer` rows were never persisted to the schema
**Chose:** insert a `Customer` row (`bank_id`, `segment`, `preferred_debit_day`,
`opted_out`) per customer in `sim/engine.py`, and set `preferred_debit_day` when a
date-change offer is accepted (Tier 1 evidence).
**Over:** leaving `sim.latent.CustomerLatent.bank_id` as the only place `bank_id` existed.
**Because:** discovered while building `features/` (Phase 2) — `Mandate.customer_id`
referenced a `customers` table that was never populated, so any join from `Mandate` to a
customer's bank would silently return zero rows. `bank_id` is **not** latent — a real PSP
knows a customer's bank from the VPA/routing info; only the balance process is hidden.
This was a Phase 1 gap, not a Phase 2 design choice, and had to be fixed before
`models/bank_health.py` or `features/recovery.py` could join anything. `segment` is left as
a constant `"standard"` placeholder — no real segmentation logic exists yet.

## [2026-08-25] Hazard model exposure unit — per-soft-decline-attempt, not per-calendar-day
**Chose:** `features/hazard.py`'s person-period frame has one row per `soft_decline`
attempt (the simulator's actual hazard-evaluation point), not one row per mandate per
calendar day as docs/05-ML-SPEC.md's prose literally describes.
**Over:** a full daily grid across each mandate's active life.
**Because:** `sim/engine.py` only calls `revocation_hazard()` immediately after a
`soft_decline` — never on a `hard_decline` (cycle ends without a hazard check), never on a
day with no attempt. A daily grid would be mostly structurally-zero rows, and including
`hard_decline` attempts as exposure rows would inject always-negative-label rows that
dilute the dataset without representing a real point of risk. Documented at length in the
module docstring so a future contributor adding calendar-day-driven hazard knows where the
grid would need to widen.

## [2026-08-25] Fixed: `Revocation.trigger_attempt_id` was always `None`
**Chose:** capture the just-inserted `Attempt.id` (via `session.flush()`) and set it on
the `Revocation` row when that attempt's hazard draw fires.
**Because:** needed to label the hazard model's target exactly (row is positive iff this
attempt IS the trigger). Without it, every hazard-model row would have been unlabelable.
Discovered while building `features/hazard.py`, same pattern as the `Customer` row gap
found while building `features/recovery.py` — Phase 1 wrote the schema's shape correctly
but didn't always populate every field a later phase would need to join or label on.

## [2026-08-25] Fixed: `make sim` → `make train` db-path wiring gap
**Chose:** `sim/run.py` now writes the canonical `data/dobara.sqlite3` for a single
default run (no `--seed`/`--seeds`/`--out` given); multi-seed sweeps keep the per-seed
`data/dobara_seed{N}.sqlite3` naming from `sim.engine.default_db_path`.
**Over:** leaving `models/train.py`'s `--db data/dobara.sqlite3` default pointed at a path
`sim.run` never actually produces.
**Because:** discovered by literally running `make sim` then `python -m models.train` back
to back for the first time — `sim.run`'s only prior default was
`data/dobara_seed{seed}.sqlite3`, seed 0. The two commands had been tested independently
(via direct `run_simulation()` calls in tests) but never chained through their CLI
entrypoints until this point, per docs/03-TECH-STACK.md's `git clone && make demo`
reproducibility contract.

## [2026-08-25] Corrected: the hazard headline number does not confirm the thesis
**Chose:** stopped describing the revocation hazard model's headline result — hazard rises
0.113 → 0.130 → 0.207 as same-cycle failure count goes 0 → 1 → 2 — as empirically
confirming the thesis, everywhere that framing appeared (`PROGRESS.md`, `models/hazard.py`
docstring). Added a "Circularity and what our numbers can and cannot show" section to the
README stating the correction explicitly.
**Over:** the framing used through Phase 2, that the rising marginal hazard was empirical
support for "aggressive retrying costs mandates."
**Because:** `sim/params.yaml`'s `revocation.hazard_per_failure_notification` (0.098) is a
declared `assumption`, recalibrated on 2026-08-25 specifically to hit the
revocations/execution target ratio — i.e. the rising-hazard-with-failures relationship was
authored into the generator by hand. A model that recovers a relationship we put there
ourselves has not validated anything about the world; it has validated that the model is
correctly specified and can recover a known relationship from data it was trained on. This
is the exact circularity the hidden-latent-state design (`sim/latent.py`, import-isolated
from `features/`) exists to prevent elsewhere in the project, and it slipped through here
because the hazard *parameter*, unlike balance/income, was never treated as something the
model needed to be protected from recovering trivially.
**What actually supports the thesis**, none of it a fitted parameter: (1) the regulatory
mechanism — every retry legally requires its own 24h pre-debit notification
(`docs/01-REGULATORY.md`, RBI-PDN-24H), so retry volume mechanically drives notification
volume; (2) the published NPCI figures — 20M revocations vs 808M executions per month,
Business Standard 2025, already pinned in `docs/04-DATA-MODEL.md`; (3) those revocations
are attributed in the source to low balance, i.e. the population this project is trying not
to harass into revoking. These are facts about the world; the hazard model's fitted
coefficient is not one of them.
**What Phase 4 needs to establish instead** to make an empirical, non-circular case:
across the *full* declared `sensitivity_range` [0.05, 0.15] of
`hazard_per_failure_notification` (`sim/params.yaml`), Dobara beats `aggressive_8x` on net
LTV — plus the break-even value of that parameter below which `aggressive_8x` would win.
This is already scoped in `docs/07-EVAL-SPEC.md` and tracked in `PROGRESS.md` Phase 4 as
the sensitivity analysis and break-even statement gate items.
