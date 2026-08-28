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

## [2026-08-25] Phase 3 agent: model loading, feature attribution, ESCALATE_TO_HUMAN scoring
**Chose, three related design calls not fully specified by `docs/06-AGENT-SPEC.md`:**

1. **Model loading.** Phase 2 (`models/recovery.py`, `models/hazard.py`) only trained and
   persisted joblib artifacts — nothing loaded them back for inference. Added
   `load_recovery_model`/`load_hazard_model` (read by exact filename convention
   `_persist` already wrote) and `predict_lgbm_contrib`/`predict_contrib` methods (native
   LightGBM `pred_contrib`) directly onto `TrainedRecoveryModel`/`TrainedHazardModel`,
   and a single I/O-boundary function `agent/models.py::load_model_bundle` that also
   builds the LTV life table and loads bank-health snapshots. **Over:** a separate
   `agent/` -owned loader duplicating the joblib filename convention, or a lazy/cached
   loader inside `decide()` itself. **Because:** `decide()` must stay I/O-free per spec;
   the loading logic belongs next to the persistence logic it mirrors, not in a third
   place.
2. **Per-decision feature attribution** (the Phase 2 item `PROGRESS.md` deferred here).
   Used LightGBM's native `pred_contrib=True` (real per-row SHAP-style values, not the
   model's global feature importance) rather than adding a SHAP dependency — LightGBM
   already computes the same Saabas-style contributions internally, so this is zero new
   dependencies and zero new numerical approximation.
3. **`ESCALATE_TO_HUMAN` scoring.** `docs/02-ARCHITECTURE.md` lists it as "always in the
   candidate set" alongside `STOP`, but the formal `E[net|a*]>0 else STOP(...)` decision
   rule only names `STOP` as the sub-zero fallback — it doesn't say what beats what
   between `STOP` and `ESCALATE_TO_HUMAN` when neither is preferable to a real action.
   **Chose:** both scored at a flat `E[net]=0.0` baseline; Python's stable sort plus
   `STOP` being listed first in the candidate list means `STOP` wins ties. `ESCALATE_TO_HUMAN`
   is therefore fully reachable, gated, and scored in this build — it appears in
   `rejected_alternatives` whenever it loses — but its actual *selection* as the emitted
   action, rather than a considered-and-declined alternative, has no forcing trigger yet
   and is deferred to the human-facing proposal queue (Phase 5). **Because:** inventing a
   forcing condition not named anywhere in `docs/01-REGULATORY.md` or
   `docs/06-AGENT-SPEC.md` would be guessing at unwritten policy; `requires_signoff`
   (above `human_signoff_threshold_inr`) already carries the real "needs a human"
   signal the spec describes, decoupled from which specific action is chosen.

**Also resolved, smaller:** the spec lists `INSUFFICIENT_CONFIDENCE` as stopping reason
#7 (`docs/02-ARCHITECTURE.md`) but also describes a distinct `ABSTAIN(reason)` action
whose own reasons are the four abstention triggers (`docs/06-AGENT-SPEC.md`). Resolved
as: `Decision.chosen` is `Abstain(reason=<one of the four AbstentionReasons>)`, and
`Decision.stopping_reason` is set to `StoppingReason.INSUFFICIENT_CONFIDENCE` alongside
it — the two enums answer different questions (what action was taken vs. which of the
seven named reasons explains a non-normal outcome) and both fields are populated
together rather than picking one representation over the other.

**Also, honestly scoped down:** `OfferDateChange`'s `E[net]` is a flat placeholder
(`0.01`, just above the `Stop`/`EscalateToHuman` zero baseline) rather than modelled —
its real value depends on the date-change offer's response rate, which is an eval-harness
mechanic (`docs/07-EVAL-SPEC.md`, the `response_rate: 0.0` required run), not something
`decide()` can compute from a single `DecisionContext`. It is gated exactly like every
other candidate and appears in the audit trail, just not numerically optimized against
in Phase 3. `SendPreDebitNotice` is similarly never generated as a free-standing
top-level candidate — every notice in this build serves a specific proposed debit, so
there is no scenario with a distinct scoreable value for sending one on its own; the type
still exists for the compliance gate and a future reminder-only extension.

**Confidence interval, stated as an approximation, not a posterior.** Neither model
exposes a per-prediction predictive distribution. `agent/decide.py` approximates the CI
on a candidate's `E[net]` with a normal approximation to the binomial proportion CI
(`p ± 1.96·sqrt(p(1-p)/n)`), using each model's training-time slice observation count as
the effective sample size, propagated through the linear `E[net]` formula by interval
arithmetic. This correctly widens for thin slices and tightens for well-observed ones and
is fully reproducible, but it is not a calibrated posterior — documented as such directly
in `agent/decide.py`'s module docstring so it cannot be mistaken for one later.
**Superseded by the two entries below, 2026-08-25** — both the naming and the formula
changed before Phase 4 added any more call sites.

## [2026-08-25] `confidence_interval` renamed to `confidence_band`
**Chose:** renamed `Decision.confidence_interval` (and the internal `_Score.ci_lo/ci_hi`,
now `band_lo`/`band_hi`) to `confidence_band` everywhere in `agent/` — the dataclass
field, `agent/decide.py`'s docstrings, `agent/audit.py`'s renderer, plus the pseudocode in
`docs/06-AGENT-SPEC.md`, the entity list in `docs/04-DATA-MODEL.md`, and the DB column
`sim/schema.py::Decision.confidence_band_json` (unused so far — no persistence code reads
or writes it yet, so this was a free rename with zero call sites to break).
**Over:** leaving it named `confidence_interval`, which is also what Phase 4's eval
harness will call its own bootstrap/seed-variance intervals over `artifacts/summary.json`.
**Because:** the two are statistically unrelated — one approximates uncertainty in a
single calibrated probability at decision time from a slice's observation count; the
other measures variance across simulated seeds of a fully-run evaluation arm — and both
being called "CI" would let this acknowledged approximation quietly borrow the authority
of a sound estimate wherever it's displayed (an audit card, `/evidence`). Doing this now,
before Phase 4 writes any evaluation-CI code, avoids ever having two same-named,
differently-sound quantities in the same report. "CI" is now reserved exclusively for
Phase 4's evaluation output.

## [2026-08-25] Per-decision band switched from the normal approximation to Wilson
**Chose:** `agent/decide.py::_wilson_interval` (was `_proportion_ci`, using
`p ± 1.96·sqrt(p(1-p)/n)`) now computes the Wilson score interval on each probability
before propagating it through the linear `E[net]` formula.
**Over:** the normal approximation to the binomial proportion CI.
**Because:** the normal approximation undercovers at small `n` and near `p` = 0 or 1 —
exactly the thin-slice, low-hazard regime `confidence_band` exists to adjudicate for
`ABSTAIN` — and is not even guaranteed to stay inside `[0, 1]` there (only rescued by the
existing `max(0.0, ...)`/`min(1.0, ...)` clamps, which mask rather than fix the
miscoverage). Wilson is bounded to `[0, 1]` by construction and well-behaved at small `n`,
without changing anything else about the approach: still per-probability, still using the
training-time slice `n` as the effective sample size, still an explicit approximation
rather than a real posterior — that limitation is unchanged and still documented in
`agent/decide.py`'s module docstring.

## [2026-08-25] `agent/decide.py` batched scoring — perf fix for Phase 4, characterization-tested
**Chose:** `agent/decide.py::_score_all` now calls `models.recovery.predict_lgbm`/
`predict_lgbm_contrib` **once** per `decide()` call (batched over the unique candidate
days) and `models.hazard.predict`/`_latest_bank_health` **once** per call (both are
`ctx`-only, so every `ScheduleDebit` candidate was already getting an identical
prediction before this change — just recomputed ~30-90 times), instead of once per
candidate. Verified behavior-preserving with a new characterization test
(`tests/test_agent_decide_characterization.py`), which snapshots the full `Decision`
output for 20 varied `DecisionContext`s against fakes whose predictions vary *per row*
(by `day_of_month`) — a constant-output fake (as used elsewhere in `tests/test_agent_decide.py`)
cannot catch a batching bug that scrambles which prediction maps back to which candidate,
since every candidate would score identically either way; this one can. Baseline fixture
captured pre-refactor, asserted byte-identical (post 6dp float rounding, to absorb
harmless floating-point-reordering noise, not real divergence) post-refactor. All of
Phase 3's existing tests (purity, 7 stopping reasons, 4 abstention triggers, the
200-example `hypothesis` property test) stayed green throughout, unmodified.
**Over:** leaving the ~90-separate-predict-calls-per-decision structure Phase 3 shipped
with, or reducing Phase 4's population/seed count instead of fixing it.
**Because:** Phase 4's eval harness calls `decide()` live for every mandate/cycle in the
`dobara` arm. Measured before this fix: 89s for 15 mandates (~5.9s/mandate), which
projects to ~8h for a single seed at `sim/params.yaml`'s default population (5000
customers) — infeasible for even one point of the sensitivity sweep, let alone the full
30-seed harness. The user was explicit this must be fixed by making `decide()` actually
faster (behavior-preserving, provably so via the characterization test), not by quietly
shrinking the population or seed count, since those degrade the things the project's
credibility rests on (CI width, the 2.5% revocation calibration target).
**Measured result:** `eval` arm smoke run (15 mandates, all 5 arms) — `dobara` arm:
89s -> 3.4s (~26x). Full-scale single-`decide()`-call benchmark against real trained
models (`data/dobara.sqlite3` artifacts): ~25ms/call. Extrapolated: ~0.227-0.29s/mandate
in the `dobara` arm end-to-end (incl. simulation-loop overhead, not just `decide()`),
confirmed at both n=15 and n=500 scale (world generation itself is negligible: 0.43s at
n=5000). At the default population (5000 customers): ~19-23 min/seed for the `dobara`
arm alone (the only arm making model calls — the other four are cadence-based and
effectively free). Also added `joblib`-based parallelization across sweep points
(`eval/sensitivity.py::sweep_hazard_per_failure_notification`'s new `n_jobs` parameter) —
each point is independent given the shared `world`, so this parallelizes cleanly.

## [2026-08-25] Sensitivity sweep — first real result: `dobara` beats `razorpay_default` across the full range, at n=500/seed=1
**Finding:** ran `eval/sensitivity.py::sweep_hazard_per_failure_notification` (5 points
across the declared `[0.05, 0.15]` range, common-random-numbers via one shared seeded
`world`, `n_jobs=5`) at `n_customers=500` (population reduced from the default 5000
*for this preliminary sweep only*, per the user's explicit allowance — "applies to the
sensitivity sweep only, never the headline 30-seed run" — flagged here and needs
flagging in the README when that section is written): **`dobara`'s mean net LTV per
mandate beat `razorpay_default`'s at every one of the 5 points**, and the margin widened
monotonically with the hazard value — exactly the mechanism the thesis predicts (higher
per-failure-notification hazard makes `dobara`'s restraint more valuable, not less):

| `hazard_per_failure_notification` | dobara mean net LTV | razorpay_default mean net LTV | dobara − razorpay_default |
|---|---|---|---|
| 0.05  | 5014.9 | 4948.0 | **+67.0**  |
| 0.075 | 4952.3 | 4794.4 | **+157.9** |
| 0.10  | 4887.6 | 4651.4 | **+236.2** |
| 0.125 | 4742.1 | 4371.0 | **+371.1** |
| 0.15  | 4626.8 | 4255.2 | **+371.6** |

**Caveat, stated honestly, not glossed over:** this is a single seed (seed=1) at a
reduced population (500 mandates, not the default 5000), with per-mandate bootstrap CIs
that still overlap substantially at the low end of the range (e.g. at 0.05: dobara
[4627, 5527] vs razorpay_default [4531, 5517]) — this is NOT yet the properly-powered,
paired-same-seed, 30-seed statistical claim `docs/07-EVAL-SPEC.md` requires for the
headline. It is a real, mechanically-sensible directional finding from a real run (not a
guess, not a forced result — the sweep was run once and reported as-is), sufficient to
proceed to the full harness rather than stop and reframe.
**Runtime measured:** 145.8s wall (2:26) for the full 5-point parallelized sweep at
n=500. Projected for the full 30-seed x 5-arm harness at the default n=5000: ~19-23
min/seed x 30 seeds / (parallelism across seeds, ~8 cores available) ≈ **60-90 minutes**,
dominated entirely by the `dobara` arm's live `decide()` calls. This is a real,
multi-tens-of-minutes-to-low-hours commitment even after the batching fix and
parallelization — the coordinator stopped here (checkpoint, not blocker) to report these
numbers before committing further session budget to that run, per the user's explicit
instruction to report speedup/runtime "before kicking off the full harness."

## [2026-08-25] Full 30-seed harness ran; two anomalies found in verification, oracle fixed

**Chose:** before accepting the completed 30-seed x 5-arm run's numbers, the coordinator
independently verified the arm-dominance structure the spec assumes (`oracle` should
weakly dominate every arm; `do_nothing` is framed as "the floor"). Two problems surfaced.

**Problem 1 — `oracle` violated the dominance property it is supposed to guarantee.**
`eval/runner.py::_run_oracle_arm` used its latent-state access only to pick *which day*
to attempt (maximizing expected balance, avoiding known outage days), then still blindly
retried up to `retry_policy.max_attempts_default_policy` times per cycle on a fixed
cadence with no stopping logic — structurally identical to `razorpay_default`'s retry
loop. Result: oracle's revocations (1,180) exceeded `razorpay_default`'s (1,049), and its
net LTV (22.69M) fell below both `do_nothing` (24.34M) and `dobara` (23.69M) — a logical
impossibility for an arm with strictly more information than every other arm.
**Fixed:** oracle now also uses its latent access to decide, before every attempt,
whether attempting is worth it — `_true_p_success` (an exact closed-form expectation over
`sim.latent.balance_available`'s log-normal noise, replicating `attempt_outcome`'s
td/bd/correlation arithmetic exactly, not a Monte Carlo approximation) and the real
`sim.engine.revocation_hazard` feed `E[net] = p_success_true*amount -
(1-p_success_true)*p_revoke_true*ltv - cost`; the cycle stops the instant this is not
positive. Verified at n=200-1000 smoke scale post-fix: oracle now weakly dominates every
other arm on net LTV, as it must.
**Because:** an oracle is only a meaningful ceiling if it is provably at least as good as
every feasible policy, including "attempt once and never retry" — using foresight for
timing alone without a stopping rule doesn't buy that; a rigorous ceiling needs the
correct expected-value accounting (weighted by true P(failure), since only a failed
attempt can trigger a revocation roll), not a copy of `razorpay_default`'s cadence.

**Problem 2 — `dobara` underperformed `do_nothing` on both gross and net LTV in the
completed run** (gross: 24.93M vs 25.25M; net: 23.69M vs 24.34M; notifications: 40,009
vs 38,742; revocations: 636 vs 395) — `dobara` made *more* attempts, sent *more*
notifications, achieved *fewer* successes, and caused *more* revocations than a policy
that never retries at all. Investigated three concrete hypotheses before deciding not to
act unilaterally:
- Confirmed `agent/decide.py`'s `E[net] = p_success*amount - p_revoke*ltv - cost` uses
  `models.hazard`'s raw output directly as `p_revoke`, **not weighted by `(1 -
  p_success)`** — but `models/hazard.py`'s training data is one row per *already-failed*
  (`soft_decline`) attempt (`features/hazard.py`'s documented exposure unit), so the
  model's output is `P(revoke | this attempt fails)`, not `P(revoke | this attempt is
  made)`. Using it unweighted overstates the downside by a factor of `1/P(fail)`. This
  exact unweighted form is also what `docs/06-AGENT-SPEC.md`'s own worked example uses
  (`E[net] = 0.71×499 − 0.038×4240 − 0.35`) — so it is a spec-level formula, inherited by
  Phase 3's implementation, not a slip introduced in this session.
- A synthetic probe comparing `models.hazard`'s predictions against
  `sim.engine.revocation_hazard`'s true values for matched contexts (failures=1..4,
  n=50 synthetic customers) found the model's predictions were *higher* than the true
  mean in every case tested — i.e. no clear evidence the hazard model *under*-prices risk,
  which would have been the simpler explanation for `dobara` over-retrying. The direction
  of the unweighted-formula question above and this calibration probe point different
  ways, and the sample was small and not matched to the actual eval population.
- Confirmed empirically `dobara` never has zero attempts on a mandate (no full-mandate
  skip) but does have lower mean successes than `do_nothing` (6.77 vs 6.85) despite more
  mean attempts (7.95 vs 7.75) and more notifications (8.00 vs 7.75) — consistent with the
  extra retries triggering more revocations that truncate mandates before they reach
  later, easier-to-bank cycles, exactly the mechanism the thesis describes, just landing
  on `dobara`'s own calibration rather than `razorpay_default`'s.
**Not fixed this session — deliberately.** Whether `agent/decide.py`'s unweighted use of
`p_revoke` is a genuine correctness bug or an intentional spec-level simplification is
unresolved, the fix would touch already-shipped, reviewed, characterization-tested Phase 3
code, and — critically — the fix happens to point in the direction that would make
`dobara` retry *more*, the "convenient" direction for this specific finding, which is
exactly the kind of change that should not be made unilaterally under time pressure to
produce a better-looking result. Reported to the user/coordinator instead of guessing.
**Because:** CLAUDE.md: "Never re-litigate a decision recorded in `docs/DECISIONS.md` or
`docs/03-TECH-STACK.md`... unless the user overrules," and this touches a formula stated
explicitly in `docs/06-AGENT-SPEC.md`'s own worked example — a change here needs the
user's sign-off, not an agent's unilateral judgment call under a "fix it" mandate that
could otherwise be read as license to tune the result toward a preferred conclusion.

## [2026-08-25] Fixed: P(revoke) was the hazard model's raw conditional-on-failure output, not the unconditional probability the E[net] formula needs

**Chose:** the user reviewed the reasoning above and explicitly authorized the fix.
`agent/decide.py::_net_score` now computes `p_revoke = (1 - p_success) * hazard_raw`
(the model's raw output renamed `hazard_raw` throughout `_score_all`/`_net_score` to make
the distinction unmissable), used in `E[net]`, `RupeeMath.p_revoke` (so the audit trail's
displayed rupee-math stays internally consistent — `rm.p_revoke * rm.ltv_remaining`
equals the actual subtracted downside), and the Wilson confidence band (propagated as a
product of two independent bounds: `p_revoke`'s worst case pairs the highest plausible
`hazard_raw` with the highest plausible `1 - p_success`, i.e. the *lowest* plausible
`p_success` — the same worst-case/best-case convention already used for `p_success`
alone). `docs/06-AGENT-SPEC.md`'s worked example updated to show both the raw conditional
value and the weighted result. `tests/test_agent_decide_characterization.py`'s fixture
deliberately regenerated (documented in the test file's own docstring) — every case's
`expected_net`/`confidence_band`/`rupee_math` shifted since `p_revoke` shrank everywhere.
`make check` green (73 tests): the purity test, all 7 stopping-reason tests, all 4
abstention tests, and the 200-example `hypothesis` property test needed no changes — none
of them hard-code a specific `E[net]` number.
**Because:** this is correct regardless of which arm it favors — `P(revoke | fail)` is
not `P(revoke)`, and conflating them is a real conditional-probability error in the money
path, independent of any eval-harness result.

**But it does NOT resolve, and mildly sharpens, the `dobara`-vs-`do_nothing` puzzle from
the entry above — reporting this honestly rather than assuming the fix worked.** Smoke-
tested at two scales before committing to the ~2h full rerun (`_run_one_seed` directly,
bypassing the harness's parquet/summary writing):
- n=400 (seeds 901-902, 200 customers each): `dobara` net LTV/mandate ₹4,470 vs
  `do_nothing` ₹4,777 — `dobara` still behind by ₹307/mandate.
- n=4,000 (seeds 901-905, 800 customers each, less noisy): `do_nothing` ₹4,829,
  `razorpay_default` ₹4,525, `dobara` ₹4,662/mandate. `dobara` beats `razorpay_default`
  by ₹137/mandate (still a real, solid margin) but trails `do_nothing` by ₹167/mandate —
  and critically, `dobara`'s mean attempts (7.95 → 8.12) and notifications (8.00 → 8.15)
  *increased* after the fix, not decreased, because shrinking `p_revoke` makes every
  retry candidate's perceived downside smaller, so `decide()` is now *more* willing to
  retry, not less. This is the opposite of what would close the gap with a zero-retry
  baseline, and it is exactly the direction the previous entry's diagnosis flagged as
  "convenient" and declined to assume — the smoke check confirms that caution was
  warranted: the fix was correct to make on statistical-correctness grounds alone, but it
  is not, by itself, the explanation for why `dobara` loses to `do_nothing`.
**Also corrects a misreading of the pre-fix headline number**, caught while computing
these per-mandate comparisons: the completed (pre-oracle-fix) run's
`paired_dobara_vs_razorpay_default.mean_diff` of ₹1,028,326.93 is the mean **per-seed**
total difference (each seed = 5,000 mandates), not a total pooled across all 30 seeds'
150,000 mandate-rows — so the correct pre-fix per-mandate lift was **≈₹205.67/mandate**,
not ≈₹6.86 as an earlier per-150,000 division implied. Worth being careful about this
distinction (`_total` metric names in `summary.json` are per-seed totals, aggregated by
`eval/metrics.py::bootstrap_mean_ci` across seeds) whenever quoting these numbers.
**Not rerun this session.** The full 30-seed harness was not relaunched: relaunching now
would only reproduce the still-unresolved `dobara`-vs-`do_nothing` question at greater
computational cost, on a premise (the fix explains the gap) the smoke check does not
support. Rerunning is worthwhile once that deeper question — whether the hazard model's
predictions, at the *specific* feature values `eval/runner.py::_run_dobara_arm` actually
presents (not the small synthetic probe in the previous entry), systematically diverge
from `sim.engine.revocation_hazard`'s true values for those same contexts, or whether
`LTV_remaining`/`agent/decide.py`'s candidate-generation coarseness is doing something
unexpected — has an answer, so the rerun's ~2h isn't spent re-discovering the same open
question. `artifacts/results.parquet`/`summary.json` remain the pre-both-fixes run and
must not be quoted anywhere; `PROGRESS.md` continues to flag them stale.

## [2026-08-25] Calibration probe: models are reasonably sound on the eval world — the `dobara`-vs-`do_nothing` gap is not explained by model miscalibration

**Investigated:** whether the recovery/hazard models (trained once on the original
seed-42 training population, `data/dobara.sqlite3`) generalize to the fresh eval-world
populations `eval/world.py` generates (seeds 101+), since a train/eval calibration gap
could bias `agent/decide.py`'s `E[net]` and explain why `dobara` retries more than
`do_nothing` while doing worse on net LTV. Method: monkeypatched
`TrainedHazardModel.predict`/`TrainedRecoveryModel.predict_lgbm` and
`eval.runner.revocation_hazard` (the ground-truth generative function) to capture
predicted-vs-realized pairs while running the live `dobara` arm at n=2,400 (seeds
901-902, 1,200 customers each) — small enough to run in minutes, matching the actual
feature distribution `agent.decide()` sees in production use (not a synthetic probe).

**Hazard model**: predicted `P(revoke | fail)` mean 0.135 vs true `revocation_hazard()`
mean 0.120 (3,030 paired observations) — a real, measurable **~12% aggregate
overestimate** (mean signed gap +0.0147), moderate correlation (0.58, structurally
capped well below 1 by `CustomerLatent.revocation_propensity` — an intentionally latent,
unobservable per-customer trait that multiplicatively scales true hazard by 0.3-1.7x per
`sim/engine.py::revocation_hazard`, so no observable-feature-only model could fully
track it, by design). **Critically, the bias direction is wrong to explain the puzzle**:
if the model overstates `P(revoke)`, `agent/decide.py` perceives retrying as *riskier*
than it truly is, which should bias `decide()` toward *less* retrying, not more — the
opposite of what would make `dobara` over-retry relative to `do_nothing`.

**Recovery model**: eval-world Brier score 0.1115 [0.1083, 0.1147] vs the
training-population test-set's 0.1219 [0.1179, 0.1260] (`artifacts/recovery_model_report.json`)
— **no degradation, if anything slightly better** (plausibly because `dobara` actively
selects better-than-average days, an easier prediction target). Reliability-diagram bins
track closely (e.g. predicted 0.85 vs realized 0.87 in the busiest bin). ROC AUC is lower
on the eval world (0.678 vs 0.735), but that reflects reduced *discrimination* from
`dobara`'s day-selection narrowing the range of days actually attempted, not miscalibration
— calibration and discrimination are different properties, and the one `E[net]` actually
depends on (calibration) holds up.

**LTV life table**: eval-world-independent (it's a pure function of the training
population's `Mandate`/`Cycle`/`Revocation` history, `models/ltv.py`), sampled directly —
survival curves decay smoothly and plausibly (e.g. `ott` category: 1.0 at age 0, 0.96 at
age 2, 0.90 at age 4, 0.85 at age 6), nothing structurally broken.

**Conclusion: no calibration bug found.** Both models are reasonably well-calibrated on
the eval world; the hazard model's modest bias, if it matters at all, works against
over-retrying rather than for it. **The `dobara`-vs-`do_nothing` gap is most likely a
genuine property of this simulated world's current parameter calibration** — at
`sim/params.yaml`'s present values (particularly `revocation.hazard_per_contact_density`
and the cumulative-failure-notification term), the true marginal benefit of a retry is
close to, or below, its true marginal revocation-hazard cost, so even a reasonably
well-calibrated agent's retries barely break even against never retrying at all. This is
not a failure of the thesis — it is an even stronger, more uncomfortable version of it
(retrying is so costly under India's notification-mandated regime that a *smart* policy
struggles to beat a *zero-effort* one) — but it is a genuine open question about whether
`agent/decide.py`'s remaining known simplifications (the coarse day/channel candidate
grid; `OfferDateChange`'s flat 0.01 placeholder `E[net]`, which could be winning
selections it shouldn't against candidates whose real cost is now correctly represented)
are contributing, versus this being an intrinsic property of the world. Not investigated
further this session — a decision point for the user on how much more time to spend here
versus accepting `do_nothing`-beats-`dobara` as a documented, honest finding alongside
the solid `dobara`-beats-`razorpay_default` headline result.

**Not modified**: `agent/decide.py`, `sim/params.yaml`, `config/policy.yaml` — no bug
found to fix, and this investigation was explicitly scoped not to hunt for one to force
onto the result. Two throwaway diagnostic scripts (`eval/_calibration_probe.py`,
`eval/_calibration_probe2.py`) were used and deleted; not part of the shipped `eval/`
module. The full 30-seed harness was not launched — that remains the coordinator's call.

## [2026-08-25] Phase 4 closed out — full 30-seed harness rerun on corrected code, `paired_dobara_vs_do_nothing` added
**Chose:** reran the full 30-seed x 5-arm harness (`python -m eval.run`, ~103 min,
`n_customers=5000`/seed) on the code with both fixes in place (the `oracle`
dominance-property fix, the `P(revoke)` conditional/unconditional weighting fix). Also
added a `paired_dobara_vs_do_nothing` entry to `eval/run.py`'s `summary.json` output,
alongside the two paired comparisons that already existed
(`paired_dobara_vs_razorpay_default`, `paired_aggressive_8x_vs_razorpay_default`) — the
prior investigation established this comparison matters enough to have its own CI, not
just a point-estimate table row, and the prior fork's report claimed it "should already
exist" but it did not, so added it. `artifacts/summary.json` was rewritten from the
existing `artifacts/results.parquet` via `eval.run`'s own private aggregation functions
(`_arm_summary`/`_paired_diff`/`_slice_*`/`_holdout_slice`) rather than rerunning the
full simulation a second time for this one addition.
**Result, verified:**
- `oracle` now weakly dominates every arm at full scale (₹24.86M net LTV, highest of
  all five) — confirms the dominance-property fix holds beyond the smoke-test scale it
  was originally verified at.
- **Headline** `dobara` vs `razorpay_default`: `dobara` wins by ₹664,275 total per
  5,000-mandate seed-population (95% CI [₹596,602, ₹724,368], significant, ≈₹133/mandate
  average) — the credible claim against the real incumbent, holding at full scale on
  fully-corrected code.
- `dobara` vs `do_nothing`: `do_nothing` still wins, by ₹1,015,417/seed-population (95%
  CI on the `dobara-do_nothing` diff: [-₹1,077,083, -₹960,917], significant; ≈₹203/mandate
  average) — consistent in sign and similar in magnitude to the pre-fix run and the
  post-fix smoke-check, confirming this is a stable result of the world's current
  calibration, not sampling noise from any one run.
- `aggressive_8x` vs `razorpay_default`: `aggressive_8x` loses by ₹1,147,525/seed-population
  (significant) — collapses as the thesis predicts; the mechanism-demonstration arm,
  never presented as a "win."
**Over:** treating either of the two earlier (pre-fix) full runs as final, or accepting
the smoke-scale numbers as sufficient for the headline claim.
**Because:** CLAUDE.md's non-negotiable that every reported number carries a source and a
CI applies as much to internal decision-making as to the README — a ~2-hour full run is
cheap relative to shipping a wrong headline number in the actual submission. The
`do_nothing`-beats-`dobara` finding is reported here with the same rigor as the headline,
per this project's stated ethos: naming a limitation ourselves is worth more than hiding
it. Not yet done, and explicitly out of scope for this entry: the money chart (a
frontend/polish deliverable), the full sensitivity sweep across every declared range
(`hazard_per_failure_notification` only, and only at reduced population — needs
rerunning on the corrected code before any break-even value is quoted), and a precise
break-even statement.

## [2026-08-25] RETRACTED: `do_nothing`-beats-`dobara` was built on a broken control arm
**Retracts:** the conclusion in the entry immediately above and in the calibration-probe
entry before it — "`do_nothing` genuinely beats `dobara`, a real property of the world."
**Chose:** nothing yet — this entry only records the retraction and root cause; the fix
and its verified consequences are in the entries that follow.
**Because:** the user caught it directly, from the numbers alone: the previous full run
reported `do_nothing` with `attempts_mean=7.75` and `notifications_total=38,742` over
150,000 mandates. A true "no recovery attempted" arm must make zero attempts and zero
notifications by definition (docs/07-EVAL-SPEC.md: "No recovery attempted. The floor.").
Root cause: `eval/arms.py::DO_NOTHING_CADENCE` had `max_attempts=1`, read (by every prior
session, including this one) as "no *retries*, but the originally-scheduled debit still
happens" — the wrong reading. Under that reading `do_nothing` was mechanically almost
identical to a single-attempt-per-cycle policy: it recovered nearly as much as every
retrying arm while sending far fewer notifications (no retries = no retry-driven hazard
exposure), which is exactly why it scored so well. The three prior investigation rounds
(oracle's dominance bug, the `P(revoke)` weighting bug, the calibration probe) were all
real, correctly-diagnosed, worth keeping — but the final conclusion built on top of them
("this is a genuine property of the world") inherited the broken control and is false.
**Lesson, stated plainly:** a control arm that quietly does something other than what it
claims to is the single most dangerous kind of bug in an evaluation harness — it doesn't
crash, it doesn't look obviously wrong in aggregate (it looked like a *plausible*,
if surprising, finding), and it silently corrupts every comparison that uses it as a
baseline. The fix below adds hard invariant tests specifically so this class of bug is
caught in seconds next time, not after a ~2-hour full run and multiple investigation
rounds.

## [2026-08-25] Fixed: `do_nothing` now makes zero attempts, zero notifications
**Chose:** `eval/arms.py::DO_NOTHING_CADENCE.max_attempts` changed from `1` to `0`.
Verified (50-mandate smoke test): `do_nothing` now produces exactly 0 attempts, 0
notifications, 0 gross recovered, 0 revocations, 0 net LTV.
**Over:** the previous `max_attempts=1` reading.
**Because:** per docs/07-EVAL-SPEC.md's arm table, `do_nothing` is "the floor" that
"establishes what is at stake" — it must recover nothing, at zero cost, so every other
arm's positive net LTV is legible as pure gain over doing nothing at all.
**A real design fact worth stating plainly, not silently deciding or working around:**
`do_nothing`'s revocations come out to *exactly* zero under the current simulator
mechanics, not "background hazard only" as a nonzero-but-small number. Confirmed by
reading `sim.engine.revocation_hazard` and `eval/runner.py::_draw_attempt`: the hazard
roll only ever happens *inside* `_draw_attempt`, triggered by a soft-declined attempt —
there is no attempt-independent ("ambient churn") revocation channel anywhere in this
codebase. Zero attempts therefore means zero hazard rolls, full stop. Building a genuine
ambient-churn mechanic was out of scope here (nobody asked for one, and inventing new
simulator behaviour to satisfy an invariant would be exactly the kind of unauthorized
scope creep this project's engineering discipline is against) — `do_nothing`'s
revocations being exactly 0 is documented as correct, not approximated.

## [2026-08-25] `Abstain` must stop, not fall back to an attempt
**Chose:** `eval/runner.py::_run_dobara_arm`'s `Abstain` branch now behaves exactly like
its `Stop` branch — no notification, no draw, break out of the cycle's attempt loop —
while still incrementing `res.n_abstentions` so the metric stays meaningful. Updated
`docs/06-AGENT-SPEC.md`'s "## Abstention" section and `agent/decide.py`'s module
docstring (both said the agent "falls back to Razorpay's documented default policy") and
`agent/audit.py`'s `Abstain` rendering (`_did_line`/`_why_line`) to match. `Abstain`
remains a distinct emitted action from `Stop` in `agent/decide.py` itself — the audit
trail should still distinguish genuine uncertainty from a confident negative-EV call —
only the caller's *handling* of an `Abstain` outcome changed.
**Over:** the original docs/06-AGENT-SPEC.md design, which deliberately chose "fall back
to the documented default policy" over "do nothing" when abstaining, reasoning that
Razorpay's own established policy is itself a safe, well-understood behaviour, not a
guess.
**Because:** the user explicitly overruled that prior design (CLAUDE.md permits
overruling a `docs/DECISIONS.md`-recorded choice when the user is the one doing it).
CLAUDE.md's non-negotiable is literally "when in doubt, the agent stops" — not "when in
doubt, defer to someone else's policy." Falling back to an attempt on `Abstain` also
meant ~25% of `dobara`'s cycle-decisions (the abstention rate observed in the prior,
now-retracted full run) were silently executing a `razorpay_default`-style attempt
instead of `dobara`'s own considered choice, which is not the agent this project claims
to have built.
**Consequence worth flagging honestly, not smoothed over:** this fix changes `dobara`'s
realized behaviour materially — it now forgoes ~25% of its cycle-decisions entirely
rather than falling back to an attempt, which measurably reduces its gross recovery
relative to every previous run in this session. See the abstention-rate investigation and
the re-run numbers below for the actual consequence on the headline comparison.

## [2026-08-25] Abstention rate investigated: real, not a target-rate retune
**Chose:** instrumented `agent/decide.py::_abstention_reason` directly (a throwaway
wrapper, not committed) against a live `dobara` arm run (n=1,500, seed=999) to find which
of the four abstention triggers actually fire and how often, and whether they're
justified. Result: `insufficient_slice_n` never fires (bank slices have thousands of
mandates, `config.min_slice_n=30` is not the binding constraint).
`expected_value_ci_straddles_zero` fires rarely (~1.7% of decisions). The two dominant
triggers are `bank_health_changepoint` (~16%) and `slice_calibration_error` (~10%),
together accounting for the observed ~25% rate.
**Finding on `bank_health_changepoint` specifically — a real, worth-noting design fact,
NOT fixed in this session:** per-bank breakdown shows the changepoint trigger fires
roughly *evenly* across all eight banks (10-19%), and the regime-shift bank (SBI, the one
bank docs/07-EVAL-SPEC.md explicitly wants `ABSTAIN` to fire for) is not even the
highest-firing bank (14.2%, mid-pack). This means the changepoint detector is not
specifically or preferentially catching the intentional regime shift — it's firing
broadly, which could mean the detector (`models/bank_health.py::detect_changepoint`,
Phase 2 code) is oversensitive to ordinary variance, or that `ModelBundle.bank_health` —
a *static* snapshot loaded once from the *training* population's realized history
(`agent/models.py::load_model_bundle`) — is a systematically imperfect stand-in for the
*eval* population's own (differently-seeded, so differently-realized) bank health, even
though the underlying bank behaviour *parameters* are identical across populations.
**Not fixed, deliberately:** this is Phase 2 code (`models/bank_health.py`) and/or a
methodological question about reusing static training-population artifacts against fresh
eval populations — the same "train once, evaluate against fresh worlds" pattern this
whole Phase 4 has followed elsewhere (models aren't retrained per eval seed either), so
it's not obviously wrong, just imperfect. Retuning `CHANGEPOINT_THRESHOLD`/
`CHANGEPOINT_WINDOW` to hit a target abstention rate would be exactly the kind of
result-shaping this project's discipline forbids. Documented here as a real, understood
cause of the ~25% rate (not an unexplained mystery number) and left as a candidate for a
future, deliberate Phase 2 revisit if the rate proves problematic in practice.

## [2026-08-25] `aggressive_8x` investigation: no bug, but the wrong metric was being asked to show it
**Chose:** instrumented `eval/runner.py::_draw_attempt` (throwaway, not committed) to
record, per cycle, how many attempts were actually used and the cycle's final outcome,
specifically for cycles whose first attempt failed — comparing `aggressive_8x`
(nominal ceiling 8) against `razorpay_default` (nominal ceiling 4, but see below).
**Found, and it is real, not a bug:** `razorpay_default`'s *effective* per-cycle ceiling
is 3, not 4 — `retry_policy.max_attempts_default_policy=4` is cut short by
`notification.fatigue_cap_per_cycle=3` (`DOBARA-FATIGUE`), which `razorpay_default`
respects (`Cadence.respects_fatigue_cap=True`) and, critically, **this is bug-for-bug
identical to `sim.engine.run_simulation`'s original Phase 1 loop** (same two params, same
`if notifications_this_cycle >= fatigue_cap and attempt_index > 1: break`) — not a new
eval-harness defect, a real, faithfully-replicated characteristic of the policy Phase 1/2
were trained against. `aggressive_8x` (`respects_fatigue_cap=False`) genuinely does reach
attempts 4 through 8 in its failing cycles (confirmed via the per-cycle attempt
distribution), while `razorpay_default` structurally never exceeds 3.
**Why the lifetime `attempts_mean` metric couldn't show this:** ~90% of cycles never fail
at all (first-attempt success rate is high by calibration), so a cadence's retry ceiling
is irrelevant to the vast majority of cycles regardless of arm — diluting any real
per-cycle difference into near-invisibility once averaged over a mandate's whole ~8-cycle
lifetime. Revocation-driven early truncation (an arm that revokes mandates faster reaches
fewer of its own later cycles) compounds this further. Measured directly (n=800,
seed=999), restricting to cycles whose first attempt failed: `razorpay_default` mean
attempts = 2.31, `aggressive_8x` = 2.77 (~20% higher) — real and measurable, just invisible
in the old aggregate.
**Fix: added the metric that actually reflects the cadence difference**, rather than
retuning anything to force the old one to show it. `eval/runner.py::MandateResult` gained
`n_cycles_with_failure`/`n_cycles_with_failure_then_recovery`/`attempts_in_failed_cycles`
(tracked in `_end_of_cycle`, now taking `res` and the per-cycle attempt count, across all
three arm-runner loops). `eval/run.py` exposes `attempts_mean_in_failed_cycles` per arm,
and `tests/test_eval_invariants.py`'s invariant 2 asserts `aggressive_8x`'s value exceeds
`razorpay_default`'s by >=10% (real margin below the ~20% observed, to tolerate seed
variance) — this passes at smoke scale (n=250, seed=777).

## [2026-08-25] Recovery-rate metric: two different definitions, now distinct by name
**Chose:** `eval/run.py`'s per-seed aggregation now computes
`recovery_rate_of_failed_cycles` (`n_cycles_with_failure_then_recovery /
n_cycles_with_failure`, tracked per-cycle, matching `sim.engine.SimSummary.recovery_rate`
exactly) as the metric any README text must quote as "recovery rate," per
docs/07-EVAL-SPEC.md's own metric-table definition ("Recovery rate % | Of failed
cycles"). The previous mandate-lifetime proxy (of mandates with `n_attempts > 1`, the
fraction that ever succeeded) is kept under the unambiguous name
`mandate_ever_recovered_rate` for continuity, explicitly marked as not comparable. Slice-
level "recovery_rate" keys (`_slice_recovery_and_net_ltv`, `_slice_outage`,
`_holdout_slice` — all mandate-lifetime-level, a different question again: "of mandates
in this slice, how many were ever collected at all") renamed to `mandate_recovered_rate`
for the same reason.
**Over:** the prior single `recovery_rate` name covering the mandate-lifetime proxy only,
which is why the (now-retracted, broken-do_nothing) full run reported 0.97-1.00 — an
entirely different, non-comparable number from Phase 1's calibration-gate benchmark of
(0.28, 0.48) (`tests/test_calibration.py`), a coincidence of naming, not of scope.
**Because:** the user asked for these to be "named distinctly, and documented which one
the README quotes." `recovery_rate_of_failed_cycles` is that one.

## [2026-08-25] Four hard invariant tests added (`tests/test_eval_invariants.py`)
**Chose:** a small-population (n=250, seed=777), fast (~55s) pytest module asserting: (1)
`do_nothing` makes zero attempts/notifications/gross-recovered, zero revocations; (2)
`aggressive_8x`'s mean attempts-in-failed-cycles exceeds `razorpay_default`'s by >=10%;
(3) `dobara`'s net LTV cannot be significantly below `do_nothing`'s (bootstrap CI on the
paired per-mandate diff must not lie entirely below zero) — logically required since
`STOP`/`ABSTAIN` (now correctly stopping, see above) are always in `dobara`'s candidate
space with a positivity floor on `E[net]`, so its worst case degenerates to
`do_nothing`'s zero-attempt behaviour; (4) `oracle` weakly dominates every arm on net LTV
and uses fewer total attempts than `aggressive_8x`. All four pass on the fully-corrected
code.
**Because:** the user was explicit — this class of bug (a control arm silently not doing
what it claims) must not be able to recur silently. These run in seconds against a small
population specifically so they can gate every future change to `eval/arms.py`/
`eval/runner.py`, not just the expensive full 30-seed harness.

## [2026-08-25] STOPPED HERE: the `Abstain`-must-stop fix flips the headline comparison — not fixed further this session, needs a decision
**Found, at smoke scale (n=600, seeds 101 and 102, both consistent):** with all the above
fixes in place, `dobara` now **loses** to `razorpay_default` on net LTV by a wide,
consistent margin — seed 101: razorpay_default ₹2,835,524 vs dobara ₹2,222,317 (dobara
-₹613,207, ≈-₹1,022/mandate); seed 102: razorpay_default ₹2,678,447 vs dobara ₹2,132,417
(dobara -₹546,030, ≈-₹910/mandate). This is not noise — it's the same direction and a
similar magnitude across two independent seeds, and it is much larger than the previous
(illegitimate, `do_nothing`-contaminated) run's reported ₹133-205/mandate *win*. All four
new invariant tests (`tests/test_eval_invariants.py`) still pass — `dobara` still beats
the *true* floor (`do_nothing`, now correctly zero) by a wide, expected margin; it is
specifically the headline comparison against `razorpay_default` that has flipped.
**Root mechanism, understood, not a new bug:** `dobara` abstains on ~25-28% of its
cycle-decisions (unchanged rate — the abstention *logic* wasn't touched, only what
happens *after* abstaining). Before the `Abstain`-must-stop fix, those ~25-28% of
decisions silently fell back to a `razorpay_default`-style attempt and often still
recovered revenue by luck; correctly making `dobara` do nothing on those decisions (per
CLAUDE.md's "when in doubt, the agent stops," and per the user's explicit direction)
removes that quietly-borrowed revenue. `razorpay_default` has no abstention concept at
all — it always attempts, per its fixed cadence — so it structurally cannot lose ground
this way.
**Why this connects directly to the still-unresolved abstention-rate finding above:**
`bank_health_changepoint` (~16% of decisions) fires roughly *evenly* across all eight
banks, not concentrated on the regime-shift bank — the one bank docs/07-EVAL-SPEC.md
actually wants `ABSTAIN` to catch. If that trigger is substantially spurious (the
detector reacting to ordinary variance, or the static training-population `bank_health`
snapshot being a poor stand-in for the eval population's own realized history — both
flagged, neither confirmed, above), `dobara` may now be forgoing real, recoverable
revenue on a large fraction of decisions for no good reason — which would make the
Phase 2 `models/bank_health.py` changepoint detector's calibration the likely deciding
factor in whether the project's headline claim holds at all, not a minor footnote.
**Deliberately not fixed further this session:** touching `models/bank_health.py`
(Phase 2, already shipped and tested) is outside what this session's directive scoped,
and — per the same standard applied throughout this investigation — a Phase 2 model
change made specifically because the headline number depends on it would be exactly the
kind of result-shaping this project's discipline forbids, even though in this case the
*direction* of a legitimate fix (a less-trigger-happy changepoint detector) happens to
also help the headline. That coincidence is precisely why it needs a second person's
judgment before touching it, not a reason to avoid ever touching it.
**The full 30-seed harness has NOT been rerun.** Rerunning it now would either reproduce
this same flipped result at full scale (informative, but the underlying cause would
still be unaddressed) or cost ~2h to learn what a few smoke-scale seeds have already
shown clearly. Stopping here to report instead, per the standing instruction: when
something looks like it needs forcing to get a specific result, stop and report rather
than picking a side.
**What IS correct and complete, independent of how the headline question resolves:** the
`do_nothing` fix, the `Abstain`-must-stop fix and its documentation updates, the
`aggressive_8x` investigation and its new metric, the `recovery_rate` metric fix, and the
four invariant tests are all real, user-authorized, and verified — committed regardless
of the open headline question, since none of them depend on its resolution.

## [2026-08-25] `bank_health_changepoint` detector recalibrated — empirically validated, narrows the gap but doesn't close it
**Chose:** replaced `models/bank_health.py::detect_changepoint`'s rolling split-half
comparator (window=8, absolute threshold=0.20) with a frozen early-history baseline
(`BASELINE_N=300` first-attempt-only observations per (bank, method), established once
and never updated) compared by two-sample proportion z-test against a rolling recent
window (`RECENT_N=100`, same first-attempt-only restriction), flagging at
`CHANGEPOINT_Z_THRESHOLD=3.0`.
**Over:** the original design, and — tried and rejected first — a version of the same
split-half design with a properly-scaled two-sample z-test at various window sizes
(8 through 150). Both alternatives were tested against the real training data
(`data/dobara.sqlite3`) before being rejected, not assumed to fail.
**Because, in order of what was actually found, not assumed:**
1. **Confirmed the diagnosis empirically first.** SBI's real first-attempt success rate
   drops 88.7% -> 79.2% from cycle 6 onward (n=2,982 pre / 1,568 post) — a large, genuine,
   easily-significant-in-aggregate effect. The old detector fired 13-18% on *every* bank
   (SBI barely distinguishable from PNB's 18.1%), confirming it was mostly noise, not
   signal — a 0.20 absolute gap on an 8-vs-8 window is only ~1.1 standard deviations at
   this simulator's realistic success rates, rechecked after every single attempt (a
   repeated-significance-testing setup).
2. **A properly-scaled z-test on the same rolling-split-half shape still failed**, and
   understanding *why* mattered: at any window/threshold combination tried (up to
   window=150, z=3.0), detection during cycles 7-8 (well past the transition, comfortably
   inside the new regime) stayed under ~2.5%, despite the large aggregate effect size.
   Root cause, found by inspecting a 100-wide rolling mean of SBI's raw outcome sequence
   directly: a **split-half** window only sees a *transition* — once both halves of the
   window are drawn from the same post-shift regime, the comparison goes quiet again,
   even though the bank remains persistently different from what the models were trained
   on. This is a structural property of the split-half shape, not a tuning problem;
   widening or raising the bar on the same design cannot fix it.
3. Separately, per-attempt outcomes are strongly retry-correlated
   (`retry_policy.within_cycle_repeat_failure_correlation=0.65`), which inflates the
   *true* variance of a per-attempt stream well past what a z-test's i.i.d. binomial
   formula assumes — restricting both the baseline and the recent window to
   **first-attempt-only** observations (one per mandate-cycle, much closer to
   independent) fixed this.
**Validated, not assumed, before shipping:** `BASELINE_N=300`/`RECENT_N=100`/`z=3.0`
against the real training data gives a ~0.2-0.5% false-positive rate on the seven
unaffected banks and 55-70% detection specifically for SBI through cycles 6-8,
*persisting* for the whole shift window (unlike the split-half design). Two regression
tests added (`tests/test_bank_health.py::test_changepoint_low_false_positive_rate_on_a_stable_series`,
`test_changepoint_detects_a_sustained_shift`) lock in both properties against synthetic
series, independent of this specific training run. `BankHealthSnapshot` rows regenerated
against `data/dobara.sqlite3`; `models/train.py` already calls
`compute_bank_health_snapshots` on every training run, so this requires no extra wiring
for a fresh `make train`.
**Consequence, measured, not assumed:** at smoke scale (n=600, seeds 101/102, unchanged
from the prior session's numbers for direct comparison): abstention rate fell from
~25-28% to ~14-17%. `dobara`'s loss to `razorpay_default` narrowed from -₹1,022/-₹910 per
mandate to **-₹348/-₹430 per mandate** — same direction, roughly a third the previous
magnitude, but still a loss, not a win.
**Deliberately stopped here, not extended further:** per the standing instruction in this
investigation (report honestly rather than force a result), the full 30-seed harness was
NOT rerun — it would either reproduce this same still-negative result at full scale
(informative, but the deciding question would remain open) or cost ~2h to learn what two
smoke-scale seeds already show clearly. The other dominant abstention trigger identified
earlier this session, `slice_calibration_error` (~10% of decisions, second only to
`bank_health_changepoint`'s original ~16%), was **not investigated in this pass** — out
of this session's authorized scope (fixing the changepoint detector specifically), and a
real candidate for the next round: whether it's a second instance of the same class of
miscalibration, or a legitimate reflection of the recovery model's real calibration gap
on this bank/method slice, is unknown.

## [2026-08-26] Static per-bank Brier abstention check removed
**Chose:** removed the recovery model's per-bank static Brier-score check from
`agent/decide.py::_abstention_reason`'s `slice_calibration_error` trigger, leaving
`min_slice_n`, `bank_health_changepoint`, the hazard model's method-slice Brier check,
and the `E[net]` confidence-band-straddles-zero check in place. Updated
`agent/decide.py`'s module docstring and `docs/06-AGENT-SPEC.md`'s "## Abstention"
section to match; no test needed rewriting (`tests/test_agent_decide.py`'s
`test_abstains_on_slice_calibration_error` shares one fixture Brier value across both the
recovery and hazard slices, so it still exercises the surviving hazard-slice path
unchanged).
**Investigated first, not assumed** (prior session, same day): confirmed empirically that
only `SBI` (the regime-shift bank) exceeds `config.max_slice_brier` (0.179 vs 0.15;
next-highest bank 0.134). That Brier score is a single number measured once, at training
time, on the test-split cycles (6-8) — exactly the window `SBI`'s regime shift is active
in. Direct instrumentation of live `decide()` calls confirmed the check fired on `SBI`
decisions across cycles 1, 3, 5, 6, 7, 8 alike — including cycles 1-5, where the eval
world's own `SBI` mandates are not yet regime-shifted (`regime_from_cycle=6`, same as
training) and the model's calibration is presumably fine. With `SBI` ~1/8 of the bank
population, this meant `dobara` abstained on that whole 1/8 of the eval population for
its entire 8-cycle mandate life, not just the 3 cycles where the concern is real.
**Over:** keeping the static check alongside the now-recalibrated `bank_health_changepoint`
detector (previous entry, same day) — the two triggers were not doing different jobs. The
change-point detector's whole purpose is "this bank is behaving differently than the
model was trained on, right now" — the exact concern the static Brier check was a worse,
time-blind proxy for.
**Because:** a number computed once, from a single historical window, cannot distinguish
"this bank is currently degraded" from "this bank was degraded three months of simulated
time ago and I still haven't updated." Once the change-point detector was fixed to
actually have the temporal precision this problem needs (previous entry: ~0.2-0.5%
false-positive, 55-70% true-positive specifically through `SBI`'s real shift window), the
static check could only ever fire as an uncaught false positive — it had no path left to
be right that the change-point detector wasn't already catching more precisely.
**Tradeoff, stated plainly:** `dobara` will now act on `SBI` during its genuinely-degraded
cycles 6-8 in the ~30-45% of cases the change-point detector's true-positive rate misses.
This is a real, smaller residual risk, not zero — but it replaces "abstain on this bank
unconditionally, forever, including when there's nothing wrong" with "abstain when there's
actual, currently-detected evidence something is wrong, most of the time." The latter is
the more honest version of the graceful-failure design `docs/06-AGENT-SPEC.md` describes.
**Measured, not assumed:** smoke-scale (n=600, seeds 101/102, same seeds as every prior
check this session for a clean series): `dobara` vs `razorpay_default` net LTV per mandate
went from -₹348/-₹430 (post-change-point-fix, pre-this-fix) to **+₹116.08 (seed 101) /
-₹99.81 (seed 102)** — split seeds, near parity, a dramatic further narrowing from the
original -₹1,022/-₹910. This is close enough, and the two seeds disagree on direction
narrowly enough, that only the full 30-seed harness with proper bootstrap CIs can actually
resolve whether `dobara` beats, ties, or loses to `razorpay_default` — reported here as an
open question pending that run, not decided from two seeds. All four invariant tests
(`tests/test_eval_invariants.py`) still pass at this scale. Full 30-seed x 5-arm harness
launched (`nohup ... &`, PID recorded in session notes, log at `/private/tmp/eval_run3.log`,
~2h projected) — not yet complete as of this entry; the next session/agent must pick up
the result before quoting any final number. **That run was later killed unfinished** (9/30
seed-tasks done after 7+ hours, far past the ~2h estimate, and the user needed the machine)
— `artifacts/results.parquet`/`summary.json` were never written by it; the next entry below
starts from a fresh diagnostic, not this run's output.

## [2026-08-26] Step 1 decomposition: abstention is small now, and it is the whole gap

**Investigated, not assumed**, per the user's explicit instruction to decompose before
touching `models/bank_health.py` again. Built a diagnostic script
(`scripts`-equivalent, run from scratch, not committed — see session notes) that replays
`eval/runner.py`'s exact `dobara` and `razorpay_default` cycle loops side by side over the
same `World`, using `eval.rng.event_rng`'s per-(mandate, cycle, attempt, kind) keying so
both arms consume identical draws for identical cycles even though `dobara` sometimes makes
zero attempts where `razorpay_default` makes several — this is what makes the "same subset
of cycles" comparison paired rather than approximate. Smoke scale, n=600, seeds 101/102
(same seeds as every entry in this file so far).

**The split is no longer ~73/27.** The two fixes already on `main` (change-point
recalibration, static-Brier removal) pushed real abstention down to **3.0-3.5%** of
paired decision-cycles. A further 2.2% are a confident `Stop(NEGATIVE_EXPECTED_VALUE)` —
not abstention, a different `AbstentionReason`-free code path — kept as a separate bucket
rather than folded in, since the two mean different things (uncertain vs. confidently no).
**94.3-94.8% of cycles, `dobara` acts.**

**(a) On the acted subset, `dobara` beats `razorpay_default` on the identical cycles, both
seeds:** seed 101 +Rs.107,682 total (Rs.681.28 vs Rs.654.89/cycle); seed 102 +Rs.21,712
total (Rs.606.21 vs Rs.600.92/cycle). Per the user's own diagnostic framing: this means
**the policy is sound, and abstention is the whole problem** — not a weak-policy finding.

**(b) On the abstained subset, `razorpay_default` earns real money `dobara` forgoes:**
seed 101 Rs.111,887.57 across 153 cycles (Rs.731.29/cycle); seed 102 Rs.70,807.16 across
128 cycles (Rs.553.18/cycle) — both figures larger than what (a) gained, which is why the
net headline stays near parity/negative even though the acted-subset comparison alone
looks like a clean win.

**(c) 100% of abstentions are `bank_health_changepoint`** in both seeds — `min_slice_n`,
`max_slice_brier` (hazard method-slice), and the `E[net]` CI-straddle never fired at this
population scale. This matches `agent/decide.py`'s abstention ordering (change-point is
checked before the Brier/CI triggers, so once it fires nothing downstream is reached) and
Step 1c's brief was specifically to attribute the 27% figure the user started from — the
true figure is ~3.2% and it is entirely one trigger.

**(c2), the finding that actually matters for Step 2:** checked firing location against
the simulator's *known* injected regime (`SBI`, `cycle_index >= 6`, `sim/params.yaml`).
Precision is decent — seed 101: 87.6% true-positive-window, 5.2% `SBI` but wrong window,
7.2% wrong bank entirely (100% of that 7.2% on `AXIS` specifically, not spread across the
other 6 banks); seed 102: 83.6% / 4.7% / 11.7% (again 100% on `AXIS`). But a genuinely odd
signal survived: **mean net LTV per abstained cycle (Rs.731, Rs.553) is *higher* than mean
net LTV per acted cycle (Rs.681, Rs.606) under `razorpay_default`** — the detector is
firing disproportionately on cycles that, on realized draws, are *more* profitable than
average, the opposite of what a correctly-targeted degradation signal should produce. This
is precision-only (measured over the fired set); **recall was not measured in this pass**
(what fraction of true `SBI, cycle>=6` decision points get flagged, in the live eval world
specifically, not the training population) — that is Step 2's job, not this one's.
Reported as-is, per the user's "report before proceeding," before any further change.

## [2026-08-26] Step 2 — pre-registered acceptance criteria, committed BEFORE the fix or rerun

Per the user's explicit instruction: these criteria are fixed in writing, in this commit,
**before** `models/bank_health.py` is touched further and **before** the full 30-seed
harness is rerun — so the git history shows the bar was set before the number was known,
not adjusted to match it afterward. Both criteria are stated **without reference to net
LTV or any eval-harness headline metric**, per the user's explicit constraint.

### 1. Changepoint detector: precision/recall against the KNOWN injected regime

Ground truth is definitional: `sim/params.yaml`'s `regime_shift.bank_id = "SBI"`,
`applies_from_cycle_index = 6`. A live `decide()`-time bank-health check is a true-positive
window iff `bank_id == "SBI" and cycle_index >= 6`.

- **Recall** (of all true-positive-window decision points, fraction where
  `changepoint_flag` fires): target **>= 50%** — a floor matching the 55-70% already
  measured on the training population (`data/dobara.sqlite3`, seed 42, prior session),
  not a new bar; the eval world is a different seed/population, so this is stated as a
  floor to not regress, not an assumption it will hold exactly.
- **Precision** (of all firings, fraction landing in the true-positive window): target
  **>= 75%** — below the 83.6-87.6% already observed in Step 1's diagnostic, since two
  smoke seeds are noisy and the bar should not be set at exactly what was already seen.
- **Uniform-firing / concentrated-false-positive check:** firing evenly across all 8 banks
  is zero discriminative power and fails this criterion outright, regardless of aggregate
  precision. Separately, false positives concentrating on one *specific* wrong bank (>50%
  of all false positives landing on a single non-`SBI` bank) also fails it and must be
  explained — Step 1 found 100% of both seeds' wrong-bank firings on `AXIS` specifically,
  which is either a real, second, undiagnosed defect (something about `AXIS`'s simulated
  profile resembles a shift) or a false-positive-count too small to read (11 and 15 events)
  to distinguish from noise. Whichever it is must be stated in the write-up, not silently
  passed because aggregate precision cleared the bar.
- Measured on **live eval-world `decide()` calls** (the same paired-cycle instrumentation
  Step 1 used), not only re-checked against the training population — the two are
  different populations/seeds and this gate is about eval-world behavior specifically.

### 2. Abstention thresholds re-derived from held-out slice-level Brier, not chosen a priori

- **`min_slice_n`**: unchanged at 30. Already tied to `models/metrics.py::MIN_SLICE_N`,
  the same constant used everywhere else in this project to decide "a slice metric is
  reported as insufficient rather than guessed" — this already *is* the calibration-derived
  floor the user is asking for; there is nothing to re-derive.
- **`max_slice_brier`** (feeds `SLICE_CALIBRATION_ERROR`, currently checked only against
  the hazard model's `by_method` slice in `agent/decide.py::_abstention_reason`):
  re-derive as a **Brier Skill Score against the climatological baseline on the same
  held-out slice**, not a hand-picked constant — abstain when
  `BSS = 1 - brier_model / brier_climatology <= 0` (the model provides no calibration value
  over predicting the slice's own marginal event rate), computed from
  `models/hazard.py::_slice_metrics`'s already-existing held-out Brier per slice at every
  `make train` run, never hand-typed into `config/policy.yaml` again.
- **Known limitation, stated honestly rather than hidden:** `METHOD` is hardcoded to a
  single value (`"upi_autopay"`) everywhere in this simulator (`eval/runner.py`'s own
  module docstring), so the hazard model's `by_method` slicing produces exactly **one**
  slice — there is no second slice to compare a percentile-style rule against, and Step 1
  already found this trigger fired 0% of the time in both seeds. If BSS-vs-climatology on
  that single slice also produces zero firings, that is an **acceptable, reported outcome**
  — "this trigger structurally cannot discriminate in a single-method simulator," not a
  bug to fix by inventing slices that do not exist. `models/hazard.py::_slice_metrics`
  already separately computes a `by_regime_shift_bank` pair (two real slices, each with a
  held-out Brier) — noted here as the fallback reference for a future session if
  `by_method`'s permanent dormancy needs a second look, **not implemented in this pass**
  (out of Step 2's scope, which is re-deriving the existing threshold's *value*, not
  changing which slice dimension it's checked against).

### What a miss means

If the recalibrated detector still misses recall, precision, or the concentrated-false-
positive check after implementation, that is reported as a miss in Step 3's write-up and
the harness is rerun anyway, per the user's explicit "do not retune, do not narrow the
reported range" — this entry exists so a miss is legible as a pre-stated miss, not
silently re-targeted to match whatever the fix actually produced.

## [2026-08-26] Step 2 results: criterion 1 measured against the pre-registered targets

Measured directly against `models/bank_health.py`'s existing snapshot table
(`data/dobara.sqlite3`, as-of-joined at each mandate-cycle's `due_date`, independent of
`decide()`'s scoring branches — see the criterion's own text above for why), smoke scale,
seeds 101/102, n=600 each, no code touched yet.

- **Recall: 65.9% (seed 101), 63.3% (seed 102) — PASSES the >= 50% target**, consistent
  with the 55-70% already measured on the training population.
- **Precision: 88.4% (seed 101), 84.2% (seed 102) — PASSES the >= 75% target.**
- **Concentration check: FAILS both seeds.** `AXIS` accounts for 14/23 (60.9%, seed 101)
  and 18/25 (72.0%, seed 102) of all false positives — both over the 50% fail line.

**Root-caused, not left as an unexplained miss.** Queried `models.bank_health`'s snapshot
table directly, per bank, for the whole training run: **6 of 7 non-`SBI` banks have a
true 0.00% changepoint-flag rate** (`BOB`, `HDFC`, `ICICI`, `KOTAK`, `PNB`, `YES` — zero
flagged snapshots each, out of ~5,000-5,400 per bank). `AXIS` alone has 89 flagged
snapshots (1.67%), forming **one sustained episode from 2026-03-27 to 2026-08-12** — not
scattered blips, a single ~4.5-month persistently-flagged stretch. `SBI` itself is 24.83%
flagged, 2026-04-15 to 2026-08-23, the correctly-detected real injected shift (consistent
with `applies_from_cycle_index=6` landing inside that window).

**This is a frozen-single-realization artifact, not a per-eval-seed statistical
fluke.** `models/bank_health.py`'s snapshot table is computed once from the training
population (`data/dobara.sqlite3`, seed 42) and never recomputed per eval seed — deliberate,
documented architecture (`eval/runner.py`'s own docstring: "models are trained once and
evaluated against fresh held-out populations, never retrained per eval seed"). But the
change-point detector is explicitly a *live, right-now* state check by its own module
docstring ("is this bank still, right now, behaving differently") — and a single random
excursion in one training realization's `AXIS` trajectory, once it crossed the
`CHANGEPOINT_Z_THRESHOLD=3.0` bar, persisted in the frozen table for ~4.5 months of
simulated calendar time (the detector's whole design point: once flagged, stay flagged
through a sustained shift, real or not). Every eval seed's `AXIS` customers whose cycle
`due_date` lands in that window inherit the same false alarm, deterministically, forever,
until the training snapshots are regenerated — this is why the concentration figure
recurs virtually identically across both eval seeds despite different customer sampling:
both are querying the exact same frozen table at overlapping calendar dates.

**Not fixed this pass** — `models/bank_health.py` still not touched, per the standing
instruction. Two of three criteria pass outright; the third is explained with hard
evidence (a single-bank, single-realization false alarm, not a systematic defect in the
recalibrated detector's aggregate behavior — the 7-bank false-positive rate this episode
sits inside, ~0.2-0.9% depending how `AXIS` counts, is still far below the pre-recalibration
13-18% uniform-firing state). Reported as-is for the user to decide whether it warrants a
code change (e.g. regenerating snapshots from a different/multiple training seeds,
requiring several consecutive flagged snapshots before persisting the flag, or accepting
it as documented residual risk) before Step 3's rerun.

**User's call:** accept the `AXIS` episode as documented residual risk — `models/bank_health.py`
stays untouched. Confirmed above by hard evidence to be a single-realization, single-bank
artifact, not a systematic detector defect; recorded here rather than silently fixed.

## [2026-08-26] Step 2 fix implemented: `max_slice_brier` re-derived as a Brier Skill Score

Per this file's own pre-registered rule (two entries above): replaced the hand-picked
`config.max_slice_brier = 0.15` constant with a Brier Skill Score against each slice's own
held-out climatology baseline. `models/metrics.py::metric_block` now computes
`brier_climatology` (Brier of always-predicting the slice's own marginal event rate) and
`brier_skill_score` (`1 - brier_model/brier_climatology`) for every metric block it
produces — recovery and hazard, overall and every slice — not just the one call site that
needed it, since it is the same held-out data already being scored and a second call site
computing it differently later would be a second source of truth. `agent/decide.py`'s
`SLICE_CALIBRATION_ERROR` trigger now fires on `brier_skill_score <= 0` (model provides no
calibration value over climatology) instead of comparing to a policy-file constant;
`config/policy.yaml`'s `max_slice_brier` entry removed (no longer read anywhere).
`docs/06-AGENT-SPEC.md`'s Abstention section and tunables list updated to match.

Regenerated `artifacts/hazard_model_report.json` via `python -m models.train` against
`data/dobara.sqlite3` to pick up the new fields (the live `decide()` path reads this file,
not a live computation) — confirmed by inspection: `by_method.upi_autopay` shows
`brier_score=0.1154`, `brier_climatology=0.1181`, `brier_skill_score=0.0226`. **Positive,
barely** — the model provides marginal skill over climatology on this single method-slice,
so the trigger stays dormant, exactly the outcome this file's own pre-registration
anticipated as acceptable given `METHOD` is hardcoded to one value everywhere in this
simulator (no second slice to have ever made this check discriminative). Test fixtures
(`tests/test_agent_decide.py`, `tests/test_agent_decide_characterization.py`,
`tests/test_agent_compliance.py`) updated to construct `brier_skill_score` directly rather
than a raw Brier point + external threshold; characterization fixture regenerated via
`write_fixture()`, byte-identical to before (the two abstain-trigger cases were rewritten
to hit the same trigger through the new mechanism, not a behavior change for any case).
`make check` green: 79 tests, ruff, mypy all clean.

## [2026-08-26] Step 3: full 30-seed x 5-arm rerun — headline result, published as-is

Per the user's explicit "run the full harness, publish whatever happens, do not retune."
`nohup uv run python -m eval.run`, 30 seeds x 5,000 mandates/seed, 101.0 min (no repeat of
the earlier unsupervised run's stall — that one was killed after 7+ hours for 9/30
seed-tasks; this one completed cleanly on the same machine, same code, run supervised).
`artifacts/results.parquet` (750,000 rows) and `artifacts/summary.json` written; both are
the current, trustworthy artifacts — everything on disk before this entry (from the
2026-08-25 retracted run) is superseded.

**Headline: `dobara` beats `razorpay_default` by ₹66 per mandate [95% CI ₹53.82,
₹80.63], paired difference across 30 seeds of 5,000 mandates each, CI excludes zero,
significant** (`paired_dobara_vs_razorpay_default`; the same figure stated as a
₹329,940.56 [₹269,095.77, ₹403,153.56] *total* over one seed's 5,000-mandate population —
do not divide the total by 150,000, the pooled 30-seed row count, that yields ₹2.20 and
looks like an error). `aggressive_8x` loses to
`razorpay_default` by ₹1,147,524.98, also significant (`paired_aggressive_8x_vs_razorpay_default`)
— collapses as the thesis predicts, never the headline comparison. `dobara` beats
`do_nothing` by ₹22,988,090.20, significant (`paired_dobara_vs_do_nothing`) — the
structural sanity invariant holds at full scale, no repeat of the pre-retraction logical
impossibility. `oracle` weakly dominates every arm (net LTV ₹24,864,706, highest of all
five) — the harness itself is sound.

**Mechanism, decomposed from row-level `artifacts/results.parquet`, not just the arm
table:** per 5,000-mandate seed, `dobara` gives up ₹742,361 of gross recovery (fewer
attempts, 7.77 vs 8.42 mean; fewer notifications, 39,081 vs 42,110) and buys back
₹1,072,301 of mandate value — ₹1,066,637 (99.5%) from avoided revocation loss (39% fewer
revocations, 638 vs 1,049), ₹5,665 from avoided notification spend — netting the
₹329,941 headline. `aggressive_8x` shows the inverse crossover: more gross (₹24,674,228,
between `dobara` and `razorpay_default`) but the worst net LTV of any retrying arm, driven
by the most revocations (1,353). This is the "Recover the payment. Keep the mandate."
thesis showing up in the actual 30-seed numbers, not asserted. **Credibility check:**
₹329,941 on `razorpay_default`'s ₹22.66M net-LTV base is a 1.46% lift — comfortably under
the 4-6% Razorpay's own production routing system reports (docs/07-EVAL-SPEC.md's
credibility anchor); a number near or above that range would be the bug to chase, not a
result to celebrate.

**Two lift estimates live in `summary.json`; only one is the headline, and they don't
conflict.** `permanent_holdout_arm` reports `dobara`'s served population (n=135,299)
averaging ₹4,607.23/mandate against its own same-world holdout control (n=14,701, routed
through `razorpay_default`'s cadence) averaging ₹4,509.19/mandate — a ₹98.04/mandate gap,
larger than the ₹66 headline. Reconciled, not left to collide on `/evidence`: the holdout
figure is a cleaner served-vs-control design (no cross-arm dilution) but is pooled across
all 30 seeds with **no seed-level bootstrap CI** — a point estimate, not a confidence
interval. The paired headline's denominator includes the ~10% of `dobara`'s own mandates
routed to the holdout control, which — using identical per-mandate RNG draws to the
standalone `razorpay_default` arm — contribute ~0 to the paired numerator by construction,
spreading the same underlying effect over a wider denominator. **The ₹66/mandate paired
figure, CI-backed, is the number to quote; ₹98.04/mandate is a directionally consistent,
uncertainty-unquantified second read of the same effect, not a competing estimate.**

**Bank-level slices are directional, not a second headline** — `robustness_slices.note`
in `summary.json` states plainly they're pooled across all 30 seeds' rows, not
independently seed-bootstrapped; no valid CI exists at the slice level.

**Not a uniform win, and the full-scale data confirms exactly what the smoke-scale
decomposition (two entries above, same day) predicted it would show — reported as designed
restraint with a measured price, not apologised for as underperformance.** Sliced by
`regime_shift_bank_flag` (directional, per the note above): on the 7 non-shifted banks,
`dobara` beats `razorpay_default` on mean net LTV/mandate (₹4,728.62 vs ₹4,561.88). On
`SBI`, the one bank carrying a real, *injected* shift, the change-point detector catches it
(63-66% recall / 84-88% precision against the known injected regime, measured this
session, see the pre-registration two entries above) and `dobara` correctly declines to
trust its own model there, per `docs/06-AGENT-SPEC.md`'s graceful-failure design. That
restraint has a real, measured price: `dobara`'s mean net LTV/mandate on `SBI` (₹3,673.17)
runs below `razorpay_default`'s (₹4,318.14) even as `SBI`-specific revocations are cut by
more than half (2,052 vs 5,219) — `dobara` is choosing to forgo some recoverable value on
a bank it correctly no longer trusts, rather than guess. Whether the *response* to a
correct detection should be zero-attempt abstention or a scaled-back attempt is the open
question — not detection quality, already measured as working — flagged for a future
session as the next lever to grow `dobara`'s margin beyond ₹66/mandate, out of Step 2's
pre-registered scope (detection quality and threshold derivation, not the response to a
detection).

**Published in `README.md`'s "Honest metrics" table and surrounding prose, verbatim from
`summary.json`, including the `SBI` underperformance** — per the user's explicit
instruction, this result is reported as-is regardless of direction; the ₹66/mandate
headline is real but modest, and the full account (including where it currently falls
short) is more useful than a smoothed-over win. The break-even statement (sensitivity
sweep across `revocation.hazard_per_failure_notification`'s declared range, the value
below which `aggressive_8x` would beat `dobara`) remains unbuilt — not run this session,
stated as outstanding in the README rather than implied to exist.

## [2026-08-26] Money chart built — not the crossover the spec assumed, reported as observed

Per the user's explicit ask, after the three reporting fixes above. The batch harness
(`eval/runner.py::MandateResult`) only stores final per-mandate totals, no per-cycle
timeline, so `docs/07-EVAL-SPEC.md`'s money chart ("X-axis: time horizon in cycles")
needed new instrumentation. Built as a diagnostic-style replay (not committed to the
harness, matching this session's earlier Step 1 decomposition pattern) reusing
`eval/runner.py`'s exact private helpers, checkpointing cumulative gross/net LTV after
every cycle. Single seed (301, held out from training seed 42 and the eval harness's
seeds 101-130), n=5,000 mandates, three arms (`aggressive_8x`/`razorpay_default`/`dobara`
— `do_nothing`/`oracle` omitted from this specific chart, already covered by the main
metrics table).

**Not the shape `docs/07-EVAL-SPEC.md` assumed.** The spec expected `aggressive_8x` to
lead gross the whole horizon and cross below on net partway through. The actual replay:
`aggressive_8x` trails **both** other arms on net LTV from **cycle 1** — no mid-horizon
crossover moment, a gap that opens immediately and widens every cycle (₹1.14M behind
`razorpay_default`, ₹1.48M behind `dobara` by cycle 8). Its own gross lead doesn't hold
up against `razorpay_default` either: ahead through cycle 4, overtaken from cycle 5 —
revoked mandates stop contributing future gross too, so the early gross lead erodes on
its own terms. It does stay ahead of `dobara` on gross the whole horizon (fewer attempts,
by design). Reported as observed in the README, not forced into the assumed shape.

Rendered as a static, dependency-free SVG (`artifacts/money_chart.svg`) rather than adding
`matplotlib` — `docs/03-TECH-STACK.md` already commits to Recharts for the eventual
Phase 6 frontend, and a throwaway plotting dependency for one README image would
contradict a stated tech choice. Built per the `dataviz` skill's procedure: one shared
₹ y-axis (gross and net are the same unit, never a dual-axis chart), color = arm identity
(fixed categorical slots: `dobara` blue, `aggressive_8x` orange, `razorpay_default` aqua),
line style = measure (solid net LTV, dashed gross), light/dark adaptive via
`prefers-color-scheme` in an embedded `<style>` block (renders correctly on GitHub in
both themes). The three arms' net-LTV end-of-horizon values converge within ~22px
vertically (`dobara`/`razorpay_default` only 5px apart) — stacking two-line label blocks
there would have overlapped, so end labels are spaced with a minimum gap and connected to
their real data points with leader lines, per the skill's guidance for converging series.
Verified programmatically (all coordinates in-canvas, valid XML) rather than visually —
the browser tool was unresponsive after three attempts this session; flagged, not silently
worked around by skipping verification entirely.

## [2026-08-26] Full sensitivity sweep + break-even: the finding that matters more than the one asked for by name

`eval/sensitivity.py` already existed (built earlier in Phase 4) but only compared
`dobara` vs `razorpay_default`, not `aggressive_8x` — extended to run all three arms per
swept point, plus `break_even_vs_aggressive_8x`/`break_even_vs_razorpay_default` (linear
interpolation between the two adjacent swept points where the sign flips; reported
honestly as "not found, X wins at every tested point" when no crossing exists in range,
never extrapolated past what was run). Run: single seed 301 (same as the money chart),
n=5,000 mandates, 5 points evenly spaced across the declared `sensitivity_range` [0.05,
0.15] of `revocation.hazard_per_failure_notification`.

**Against `aggressive_8x` — the comparison `docs/07-EVAL-SPEC.md` names — no break-even
found anywhere in the declared range.** `dobara` beats `aggressive_8x` at every tested
point, 0.05 through 0.15. Robust.

**Against `razorpay_default` — not named by the spec, but the more load-bearing
question, since it's `dobara`'s own headline claim, not `aggressive_8x`'s collapse, that
this number can undo — a real break-even exists.** `dobara` loses to `razorpay_default` at
the bottom of the tested range (hazard=0.05: `dobara` ₹4,876.16 vs `razorpay_default`
₹4,976.36/mandate) and wins from 0.075 upward. Interpolated crossing: **hazard ≈ 0.0738**.
The calibrated value is **0.098** — above break-even by ~0.024 (~33% relative margin),
comfortably on the winning side, and the one point on this whole range anchored to a real
published figure (`sim/params.yaml`'s own note: recalibrated to hit the
20M-revocations/808M-executions ≈ 2.5% ratio from NPCI's published numbers). The
range's low end (0.05) carries no equivalent independent anchor — a symmetric-ish declared
uncertainty band around the calibrated point, not itself sourced. **Published in the
README's "Break-even reporting" section under its own heading, stated plainly**: if the
true hazard sits meaningfully below the calibrated, NPCI-anchored value — roughly the
bottom half of the declared assumption range — `dobara` does not beat `razorpay_default`.
This is a genuinely different, more consequential finding than the one the spec asked for
by name, and is reported with equal weight, not buried under the `aggressive_8x` result
that happened to be robust. `artifacts/sensitivity.json` holds both break-even objects and
all 5 swept points with per-arm CIs. `make check` green (ruff/mypy clean on
`eval/sensitivity.py`; a pre-flight `import eval.sensitivity` + ruff/mypy pass caught a
`NameError` — missing `load_policy` import inside `main()` — before the first ~10-minute
sweep run, not after).

## [2026-08-26] Break-even strengthened with the NPCI anchor; remaining three sensitivity axes swept

Per the user's explicit instruction: judging the hazard break-even (≈0.074) only against
the declared `sensitivity_range` [0.05, 0.15] uses the weaker object to judge the
stronger one — that range is an a priori guess written into `sim/params.yaml` before any
data existed, while the calibrated value (0.098) is empirically anchored to the published
20M-revocations/808M-executions ≈ 2.5% ratio from real NPCI figures.

**Implemented**: `eval/sensitivity.py`'s `SweepPoint` now also records
`razorpay_default_revocation_per_execution_ratio` at every swept hazard value
(`sim.engine.SimSummary.revocation_per_execution_ratio`'s exact definition,
`n_revocations / n_attempts`, matching `tests/test_calibration.py`'s own benchmark).
`break_even_vs_razorpay_default` interpolates this ratio at the break-even hazard using
the same interpolation fraction as the hazard crossing itself (refactored `_break_even`
to share a typed `_Crossing` helper with the caller, rather than smuggling the bracket
points through a `dict[str, object]`).

**Result: the break-even hazard (≈0.074) corresponds to a revocation ratio of ≈1.91%,
against NPCI's published ≈2.5% — a ~24% relative shortfall, not just a point below the
calibrated value's own 0.098.** This is the stronger statement the user predicted: for
`dobara` to actually lose to `razorpay_default`, real-world revocations would have to run
meaningfully *below* what NPCI's own published data says they do — the losing region is
inconsistent with the external benchmark the calibration itself was built to hit, not
merely on the unlucky side of one guessed range. Published in the README's "Break-even
reporting" section, alongside (not replacing) the raw 33% hazard-value margin, per the
user's explicit "keep the raw margin regardless."

**Then swept the remaining three declared axes** docs/07-EVAL-SPEC.md names besides the
hazard, at the same seed/population, via a new generic `sweep_other_axes` (reuses
`_with_override`/`run_arm`, no break-even machinery — the spec only requires break-even
reporting for the hazard axis, "vary and re-rank the arms" for the other three):

- `date_change_offer.response_rate` [0.0, 0.15], **0.0 forced into the swept points
  explicitly** (not just an artifact of an evenly-spaced grid) per the spec's own words
  ("a response_rate: 0.0 run is required in eval and must not break the policy"): `dobara`
  wins at every tested point including exactly 0%. Robust.
- `notification.cost_inr.whatsapp` [0.2, 0.6]: zero measurable effect on the ranking
  anywhere in range — WhatsApp is too small a share of total notification spend.
- `ltv.margin_factor` [0.4, 0.9], **swept in place of `ltv.horizon_cycles`** — the spec
  names "LTV horizon / expected remaining cycles," but `sim/params.yaml`'s
  `horizon_cycles` leaf has no declared `sensitivity_range` (fixed at 8, sourced from
  docs/04-DATA-MODEL.md); `margin_factor` is the LTV-dollar-conversion assumption that
  actually carries one, and is the one docs/05-ML-SPEC.md's own note says exists "for the
  Phase 4 sensitivity analysis." The substitution is stated in-code (`OTHER_AXES`'s label)
  and in the README, not silent. **A second break-even exists here too**:
  `razorpay_default` beats `dobara` at the range's low end (0.40); `dobara` wins from
  ≈0.48 upward (hand-interpolated the same way as the hazard crossing, between the tested
  points 0.40/-25.82 and 0.525/+13.74). Calibrated value 0.7 sits ~46% above break-even —
  a wider margin than the hazard axis's, but `margin_factor` has no external anchor to
  strengthen the judgment the way the NPCI ratio does for hazard (`sim/params.yaml`'s own
  note: "not observed anywhere in the simulator, a pure assumption"). Reported as-is, not
  given the extra ratio treatment since no equivalent published benchmark exists for it.

All four axes' full point-by-point data live in `artifacts/sensitivity.json`
(`other_axes` key for the three new ones). `make check` green throughout (ruff/mypy clean
on the refactored `eval/sensitivity.py`, including a `_leaf` helper extracted to remove
duplicated dotted-path traversal between `_with_override` and the new axes' range lookup;
79 tests unaffected — no test imports `eval.sensitivity`).

## [2026-08-26] Money chart and money-chart-adjacent spec text corrected, not bent to fit

Per the user's explicit instruction: `docs/07-EVAL-SPEC.md`'s "## The money chart" section
and `docs/09-DEMO-SCRIPT.md`'s "The evidence" beat both described a crossover the actual
chart (two entries above) did not produce — `aggressive_8x` trails on net LTV from cycle 1
with no mid-horizon crossing, and loses its own gross lead to `razorpay_default` past
cycle 4. Both docs rewritten to state the finding actually observed, not the one assumed
when they were written before any data existed — `docs/07-EVAL-SPEC.md`'s section now
opens with an explicit "updated after the chart was built" note rather than silently
replacing the old text. `docs/09-DEMO-SCRIPT.md`'s "The evidence" beat rewritten with the
user's own suggested framing ("there is no honeymoon... every retry is a legally mandated
notification... it burns mandates faster than it collects from them") plus the two
break-even values (vs. `aggressive_8x`: none in range; vs. `razorpay_default`: ≈0.074
against calibrated 0.098). Also caught and fixed, while editing the same demo-script beat:
the "Graceful failure" row still said `Abstain` "falls back to Razorpay's documented
default" — stale since the 2026-08-25 fix that made `Abstain` actually stop (per
CLAUDE.md's "when in doubt, the agent stops"); corrected to match current behavior rather
than left as a second, smaller factual error in a doc already being edited for accuracy.
Same stale claim found and fixed in `docs/02-ARCHITECTURE.md`'s bounded-action-set table
and "`ABSTAIN` is the graceful-failure requirement" paragraph while reading it to scope
Phase 5 — three independent places had drifted from the same 2026-08-25 code change.

## [2026-08-26] Phase 5: the Control Room + evidence API, per docs/02-ARCHITECTURE.md's `api/` contract

Per the user's "shift the centre of gravity" instruction: Phase 4 is done, the
presentation layer (Phase 5 API, Phase 6 frontend, the video) is a third of the
submission and none of it existed yet.

**Built**: `api/main.py` (13 routes), `api/schemas.py` (Pydantic response contracts —
`agent/` dataclasses never carry `fastapi`/`pydantic` imports themselves, kept that way
deliberately), `api/converters.py` (the single mapping from `agent/` output to those
contracts), `api/demo.py` (a small cached demo population, `DEMO_N_CUSTOMERS=150`, seed
9001 — held out from training and every eval-harness seed), `api/razorpay_client.py`.

**`/evidence/summary` and `/evidence/sensitivity` serve `artifacts/*.json` verbatim** —
the same files the README quotes, so the API and the README can never silently disagree.
**`/queue`, `/counters`, `/audit/{mandate_id}`, `/approvals`, `/batch/stream` (SSE),
`/batch/poll`** all serve genuine live `agent.decide()` output computed by
`api/demo.py::get_demo_batch()`, which calls `eval.runner.run_arm()` for both `dobara`
and `aggressive_8x` (the comparison-toggle data) on the same demo population — never a
second, hand-rolled decision loop. Verified by hand against a running server (not just
unit tests): `/queue`'s first item carries real `expected_net`/rejected-alternatives/audit
text from actual model inference; `/counters`' `dobara` (₹759,790 net LTV) vs
`aggressive_8x` (₹714,512) on the n=150 demo population is directionally consistent with
the Phase 4 headline (`dobara` ahead) at a completely different, much smaller scale.

**A small, additive change to `eval/runner.py`** makes this possible without duplicating
the tested `_run_dobara_arm`/`run_arm` decision loop: both gained an optional
`audit_trail: AuditTrail | None = None` parameter (default `None`, so every existing
caller — the Phase 4 batch harness — is byte-for-byte unaffected); when supplied, every
live `decide()` call also appends its `(ctx, decision)` pair to it. Verified: reran
`tests/test_eval_invariants.py` + `tests/test_agent_decide_characterization.py`
immediately after this change, before writing any `api/` code, to catch a regression in
already-shipped Phase 4 numbers as early as possible — both still passed unchanged.

**`api/razorpay_client.py` is honest about what it automates vs. what it doesn't.**
Customer/plan/subscription CRUD and HMAC-SHA256 webhook signature verification
(`hmac.compare_digest`, constant-time) are real, implemented against Razorpay's
documented REST conventions. **`success@razorpay`/`failure@razorpay` outcome forcing is
NOT a server-side REST call this client fabricates** — it is Razorpay's own
Checkout/payment-page mechanism, which happens client-side; `test_mode_vpa_for()` returns
the correct VPA constant for constructing a real Checkout session rather than pretending
to trigger a subscription charge via an endpoint Razorpay's API doesn't expose that way.
Stated in the module docstring and `TEST_MODE_NOTE`, not left implicit. Every write
method raises `RazorpayNotConfigured` (a clear 503 at the route level) rather than
faking a response when `RAZORPAY_KEY_ID`/`SECRET`/`RAZORPAY_WEBHOOK_SECRET` are unset —
including recognizing `.env.example`'s own committed placeholders (`rzp_test_xxxx...`) as
"not configured," not as real credentials that would merely fail auth. Verified live
against a running server: unconfigured `POST /razorpay/subscriptions` and
`POST /razorpay/webhook` both correctly return 503; once a real webhook secret is set
(via `monkeypatch.setenv` in the test), a valid HMAC signature is accepted and an invalid
one correctly rejected with 400.

**"Actions execute as proposals, never direct rail calls" is now enforced structurally,
not just by convention** (docs/02-ARCHITECTURE.md's own words) —
`tests/test_no_llm_in_money_path.py::test_agent_package_never_calls_the_rail_directly`
(new, alongside the existing LLM-import-boundary tests in the same file) asserts `agent/`
never imports `httpx`/`fastapi`/`razorpay`/`requests`/`aiohttp`/`urllib3`, or `api`/`api.*`
itself. `agent/decide.py` choosing an action and `api/razorpay_client.py` proposing it to
the test rail stay two separate steps by construction, not just by nobody having wired
them together yet.

**Streaming is honestly paced, not honestly slow**: `/batch/stream`'s SSE handler adds an
0.08s delay between decision events purely for the Control Room's "counters climbing"
visual — the computation itself is already complete (the cached demo batch) by the time
any client connects; only the delivery is artificial, stated in `api/demo.py`'s module
docstring so this is never mistaken for the batch genuinely computing slowly.

**Not built, deliberately, and stated as such rather than silently skipped**: the `llm/`
narrative layer (root-cause narrative, Hinglish nudges, the audit "ask why" box) —
`docs/03-TECH-STACK.md` frames it as decorative polish, not evaluative; PROGRESS.md's
Phase 5 checklist never named it; and it's out of scope given the explicit instruction to
prioritize the presentation layer's core surfaces first.

**Tests**: `tests/test_api.py`, 13 tests, using the real demo batch (no mocked
`agent.decide()` calls — the point of this API layer is that it serves genuine model
output, so mocking the decision layer would not verify the actual contract) plus the
extended import-boundary test. Along the way, `make check`'s mypy invocation gained the
new `api` package (`Makefile`), and every new file passed a full ruff/mypy pass before
any live server test, not after — caught several `dict`-without-type-args /
`no-any-return` strictness issues immediately, at zero runtime cost.

**Also fixed, incidentally, while running the full suite to confirm no Phase 5
regression**: `tests/test_ltv.py`'s recurring flake (first seen earlier this session as
an isolated-pass/full-suite-fail mystery, documented but not chased then) was root-caused
this time — `ltv_high_amount == ltv_low_amount * 10` used exact float equality across two
different multiplication orders (`amount*r*m` vs `(amount*r*m)*10`), which IEEE 754 does
not guarantee bit-identical, combined with the test's nondeterministic category selection
(`next(iter({...}))` over a set, whose iteration order depends on each fresh process'
hash seed). Fixed with `pytest.approx`, the correct tool for a mathematical-property
assertion; verified stable across 5 different `PYTHONHASHSEED` values, not just re-run
once. `make check` green: 93 tests, ruff/mypy clean across the whole checked codebase
including the new `api` package.

## [2026-08-26] Data-shipping architecture, settled before any Phase 6 frontend fetch call

**The problem, found by the user before Phase 6 started:** nothing the API needs was
tracked in git. `data/dobara.sqlite3` (19 MB), `artifacts/*.json` (~72 KB — `summary.json`,
`sensitivity.json`, `money_chart_data.json`, `ltv_life_table.json`,
`hazard_model_report.json`, `recovery_model_report.json`), and `artifacts/models/*.joblib`
(716 KB, 6 files) were all gitignored. A fresh clone would 503 on `/evidence/summary` —
the single most important endpoint for a judge — and the README's own answer
(`make demo`) means a ~101-minute `make eval` nobody evaluating a submission will run.

**Fixed, in order:**

1. **`README.md`'s stale pre-eval placeholder banner removed** (line 8: "Status: in
   development... placeholders until `make eval` runs") — it directly contradicted the
   "Honest metrics" section 65 lines below, which correctly states every figure is
   quoted verbatim from a completed `make eval` run, and would be the first thing a judge
   reads.

2. **`artifacts/*.json` and `artifacts/models/*.joblib` un-ignored and committed.** These
   ARE the evidence; the repo should contain the evidence, not a promise to regenerate
   it. Kept ignored, deliberately: `artifacts/results.parquet` (16 MB — the full
   750,000-row eval harness output, regenerable via `make eval`, nobody reads it
   directly) and `*.sqlite3` (19 MB — the training DB, regenerable via `make sim && make
   train`, also the only writable-by-nature artifact, unsuited to being a committed
   file).

3. **`make demo-fixture` added** (`scripts/build_demo_fixture.py`), producing
   `artifacts/demo_batch.json`, committed. It calls `api/demo.py`'s existing
   `get_demo_batch()` (the same live `dobara`/`aggressive_8x` run through
   `eval/runner.py::run_arm` that Phase 5 already tested) exactly once and serialises its
   **API-shaped view**, not the raw dataclasses: `queue: list[QueueItemOut]`,
   `counters: CounterOut`, `audit_by_mandate: dict[mandate_id, list[DecisionOut]]`,
   `approvals: list[DecisionOut]`. This was a deliberate choice over serialising
   `DemoBatch`'s raw `World`/`ModelBundle`/`AuditRecord` objects: those aren't JSON-shaped
   (SQLAlchemy rows, LightGBM models, pandas frames) and reconstructing them from JSON
   would mean either a second parallel object model or losing fidelity; the Pydantic
   response models Phase 5 already built are the natural serialization boundary, and
   they're exactly what every route serves anyway.

   `api/demo.py` refactored around this: `DemoBatch` (raw, live-only) and `DemoData`
   (API-shaped, either source) are now separate dataclasses; `demo_data_from_batch()`
   converts one to the other and is shared by the live path and `make demo-fixture`, so
   the fixture is provably what a live process would have computed, never a hand-shaped
   approximation. `get_demo_data()` is the new single entry point every route calls: live
   (`Path("data/dobara.sqlite3").exists()`) or fixture
   (`artifacts/demo_batch.json`) transparently. `api/converters.py::compute_counters`
   changed signature from `(batch: DemoBatch) -> CounterOut` to
   `(dobara_results, aggressive_8x_results) -> CounterOut` — not just a refactor
   convenience, it removes a real circular-import risk (`api.demo` needs
   `api.converters` to build a `DemoData`; `api.converters` no longer needs to import
   `api.demo` for a type hint it can express directly).

   **Fixture size, reported as instructed: 45.9 MB** (150-mandate demo population,
   `DEMO_N_CUSTOMERS`, unchanged from Phase 5) — larger than expected, and larger than
   either of the binary artifacts kept out of git for size. Root cause, checked rather
   than assumed: 1,296 total audit records across 150 mandates, each carrying up to ~88
   `rejected_alternatives` (one per (day, channel) candidate `agent/decide.py` actually
   scored) plus an ~11.5 KB rendered `audit_text` block that restates them in prose —
   real `agent.decide()` output, not padding or a bug, and out of this task's scope to
   thin (that's Phase 3's candidate-generation design, already tested). Committed anyway,
   deliberately: it's readable text (JSON), not an opaque binary the way the parquet/db
   are, and 150 UI-scale demo mandates full audit trail is what the Control Room's
   `/audit/{mandate_id}` actually needs to serve without a live DB. Flagged here rather
   than silently shipped, so a future session can revisit `DEMO_N_CUSTOMERS` or the
   fixture's audit-trail depth if repo size becomes a real problem.

4. **Labeling, per the user's explicit "do not soften or omit" instruction:**
   `api/demo.py`'s module docstring states plainly that the fixture path is "no less
   real" than the live path for the same reason `/batch/stream`'s SSE pacing note already
   gives — the decisions were genuinely made by `agent.decide()`, just earlier. A new
   `GET /demo/meta` endpoint (`api/main.py`) exposes `{"source": "live"|"fixture",
   "note": ...}` so Phase 6's Control Room footer has something concrete to render this
   from — the footer itself is Phase 6 work, not built this session, but the data
   contract for it now exists so that instruction isn't forgotten by the time frontend
   code gets written.

5. **Deploy target settled, reversing `docs/03-TECH-STACK.md`'s original Hosting/Database
   sections (updated in place, struck through in spirit, reasoning kept for the
   record):** the deployed frontend is a **static** Vercel site reading committed JSON —
   `artifacts/summary.json`, `sensitivity.json`, and now `demo_batch.json` — never a
   deployed Python backend. Reasoning: Vercel's Python runtime plus
   `lightgbm`/`scikit-learn`/`pandas` sits at or near the unzipped function size limit;
   the free alternatives that do fit (Render, Fly) sleep when idle, and a judge hitting a
   30-60s cold-start spinner on a submission link is a worse first impression than any
   amount of "the live API is technically deployed too." The live API (`make api`, real
   `agent.decide()` calls, the Razorpay test-mode proposal endpoints) stays a documented
   **local-only** mode. Neon/Postgres accordingly drops out of the plan entirely — there
   is no deployed Python process left that would need a database. This was the right
   moment to settle it: doing so *before* Phase 6 writes its first `fetch()` call means
   the frontend data layer gets designed once, against committed JSON, rather than built
   against a live API and re-plumbed later.

`make check` green throughout (ruff, mypy on `agent models sim features eval api`,
pytest) after this session's changes.

## [2026-08-27] Phase 6 frontend, started: architecture, /evidence, /control-room, /audit, /mandate

**Scaffolded `web/`**: Next.js 16 App Router, TypeScript strict, Tailwind v4, Recharts.
`npx shadcn@latest init` hung indefinitely with no stdin available (non-interactive
harness) and made zero changes (no `components.json`, no new deps) -- killed after
several minutes, not re-attempted. Hand-built Tailwind components
(`web/components/ui.tsx`) instead; same dense operations-console register the spec asks
for, without the CLI dependency. Worth retrying interactively in a future session if the
component surface grows enough to want shadcn's primitives, but not blocking.

**Data layer, settled to match the 2026-08-26 static-deploy decision**:
`web/scripts/sync-data.mjs` copies `../artifacts/*.json` into gitignored `web/data/`
before every `dev`/`build` (npm `predev`/`prebuild` hooks) -- keeps `web/` self-buildable
in a Vercel "Root Directory: web" monorepo checkout without a second committed copy of
already-committed files. `web/lib/server-data.ts` is the only module that touches this
directory, marked `import "server-only"` so a client component importing it is a build
error, not a silent bundle-size leak. Verified after a full `npm run build`: the largest
client JS chunk is 392 KB -- the 45.9 MB `demo_batch.json` never reaches the browser.

**Every dynamic route is static-generated at build time, not server-rendered per
request**: `/audit/[id]` and `/mandate/[id]` call `generateStaticParams()` off
`demo_batch.json`'s own mandate ids (150 of each, 306 pages total including `/`,
`/evidence`, `/control-room`). `next build` confirms all of them prerender as static
HTML (`●` in the build's route table). This is a stronger reading of "static Vercel
deploy reading committed JSON" than merely "no Python backend" -- after build, the
Control Room's audit trail and mandate timelines need no runtime compute at all, Node
included. The Control Room's live-feeling "streaming reveal" of the case queue
(`components/control-room/ControlRoomClient.tsx`) is therefore an honestly-labeled
client-side replay of already-computed data, the same framing `api/demo.py` already
committed to for its own SSE pacing -- stated in the page footer, not left implicit.

**Caught live, not in review**: `artifacts/summary.json` contains bare `NaN` tokens --
Python's `json.dump` default serialization for `float('nan')` (e.g. `do_nothing`'s
`recovery_rate_of_failed_cycles`, undefined because zero attempts happened, by
construction). Valid for Python's own `json.load`, not standard JSON --
`JSON.parse` threw immediately, crashing `/evidence` with a 500 the first time the page
was requested. Fixed in `server-data.ts`'s `readJson()`: regex-normalize bare `NaN` to
`null` before parsing (the metric truly has no value at `n_seeds: 0`, so `null` is
correct, not a `0` that would misrepresent it as measured).

**Design tokens** (`web/app/globals.css`) instantiate the `dataviz` skill's reference
palette (`references/palette.md`) verbatim, dark-first per
`docs/08-FRONTEND-SPEC.md`'s "Dark, dense, precise. Operations-console register.":
`data-theme="dark"` stamped on `<html>` by default in `layout.tsx`, light values still
fully defined on bare `:root` for `prefers-color-scheme` and an eventual toggle (no
toggle UI built yet -- the CSS supports one). Categorical arm colors assigned by
narrative role, not palette order: `dobara` gets slot 1 blue (the star), `oracle` gets
slot 3 aqua (the ceiling, deliberately not styled as a competitor), `do_nothing` gets
muted gray (the null arm, not a categorical series). The money chart
(`components/charts/MoneyChart.tsx`) toggles between net LTV and gross recovered rather
than plotting both at once -- five arms × two measures on one chart was the dataviz
skill's "too many series, plus a dual-axis temptation" anti-pattern; a toggle keeps one
axis, one measure, five direct-labeled lines.

**Not yet done, explicitly flagged rather than silently skipped**: the Chrome extension
was unresponsive for the entire session (stuck on `tabs_context_mcp`, three retries,
never a screenshot). Correctness was verified by `tsc --noEmit`, `next lint`, a full
`next build` (all 306 pages generate), and HTML-content assertions via `fetch()` against
the dev server -- **no page has been visually confirmed to render correctly in a
browser**. `npm run dev` was left running on `localhost:3000` for a human check. The
money/sensitivity/reliability charts pass CSS custom properties (`var(--arm-dobara)`
etc.) as Recharts' `stroke`/`fill` props, which become SVG presentation attributes --
this is a common, generally-supported pattern in modern browsers, but is untested in an
actually rendered SVG this session and is the first thing to check visually. Also not
built: the `/audit` "ask why" LLM box (spec's own first scope-cut if time is short), a
theme-toggle control, and the approval-queue UI's rendering with a non-empty case (the
current demo population has zero sign-off-required decisions).

## [2026-08-27] Three findings from a static review of the committed fixture, before more frontend work

The user reviewed the committed `artifacts/demo_batch.json` and `summary.json` without a
browser (the Chrome extension was unresponsive for both of us) and found a real
correctness issue in `agent/decide.py`, not just a data-shipping one. Fixed in order.

### 1. 76% of decisions tie exactly at the argmax — diagnosed, then fixed at the root

**Measurement**: of 1,279 committed decisions with alternatives, 972 (76%) have an exact
tie at the top of the argmax; 878 of those span different calendar dates, some a month
apart. `agent/decide.py`'s sort was `scored.sort(key=lambda pair: pair[1].expected_net,
reverse=True)` — Python's stable sort means a tie always resolved to whichever candidate
`_generate_candidates` emitted first, an accident of loop order (day-then-channel), never
examined or tested as a decision rule. The audit trail rendered every tied candidate
individually as `"E[net] lower by Rs.0.00 than the chosen candidate"` — up to 88 per
decision — which states a reason that does not exist.

**Diagnosed before fixing, per the user's explicit instruction — the real mechanism is a
third thing, not either of the two hypothesized:**
- **Not "no date signal"**: the trained LightGBM recovery model has real, nonzero gain on
  `day_of_month` (1248.89) and `bank_dow_profile` (479.37) — confirmed via
  `booster.feature_importance(importance_type="gain")` — and `sim/engine.py:119`'s
  `bank.dow_weights[at.weekday()]` genuinely varies technical/business decline rates by
  weekday in the simulator itself, so this is real, not spurious.
- **Not a plumbing bug**: reproduced by monkey-patching `TrainedRecoveryModel.predict_lgbm`
  to capture both the raw booster output and the calibrated output for one live
  `get_demo_batch()` run. Raw booster predictions for mandate 0's first decision, 9 days
  spanning Aug 29 – Sep 18, ranged 0.836–0.862 — genuinely different per day, correctly
  reaching the scorer.
- **The actual mechanism: the isotonic probability calibrator is too coarse.**
  `lgbm_calibrator` (`sklearn.isotonic.IsotonicRegression`, fit on `n_validate=4,653`
  rows) has only 33 knots and **17 distinct output values across the full [0,1] domain**
  — e.g. every raw probability in `[0.860746, 0.882259]` (a 0.0215-wide band) calibrates
  to the identical `0.864548`. Confirmed directly: the same 9 raw predictions above
  (0.836–0.862) calibrate to `0.85714286` for 8 of them and `0.86454849` for 1 — the
  calibrator, not the model, erases the day signal the model correctly learned. Same
  mechanism explains why `cost` never discriminates within a tied group: `push` is
  assumption-priced at ₹0 (`sim/params.yaml`, "in-app push assumed free at our scale"),
  so identical calibrated `p_success` at identical `push` cost is an identical `E[net]`
  by construction, not a second bug.

**Fixed, as an upgrade per the user's framing, not a patch:**
- `agent/decide.py::_tie_break_score` — new, explicit, tested secondary sort key.
  Restraint decides when the money model is indifferent: prefer the `ScheduleDebit`
  candidate closest to the customer's declared preferred day when one exists
  (`ctx.has_declared_preferred_day`), otherwise the earliest legal date (for
  `ScheduleDebit` and `OfferDateChange` alike) — resolving sooner bounds how many further
  attempts/notifications a mandate can still generate, the same
  fewest-notifications/lowest-burden principle the motto already states, applied to the
  one axis a single-decision tie-break can actually control. `Stop`/`EscalateToHuman`
  (no `t`) are unaffected; their own tie (both scored `0.0`) still resolves by the
  pre-existing, already-documented "`Stop` listed first, stable sort" convention.
- `agent/decide.py::_rejected_alternatives` — collapses **every** run of mutually-tied
  candidates in the sorted list into one summary `RejectedAlternative`, not just the ones
  tied with the winner. First cut only collapsed the top tie (45.9 MB → still 45.9 MB
  fixture, no visible change) because the calibrator's coarse steps produce **one tie
  cluster per channel** (push/sms/whatsapp each land in their own plateau), not only at
  the argmax — the second-place `sms` cluster was still repeating "lower by Rs.0.15" 17+
  times. Fixed by walking the already-sorted `rest` list once and grouping every
  contiguous run of equal `expected_net`, not just the prefix equal to `best`.
- New tests: `test_tie_break_prefers_earliest_date_with_no_declared_preference`,
  `test_tie_break_prefers_closest_to_declared_day` (`tests/test_agent_decide.py`) —
  both use the existing constant-output fake model (which already ties every candidate
  by construction) and assert the *specific* chosen date, not just that some
  `ScheduleDebit` was chosen. `test_escalate_to_human_is_always_a_considered_candidate`
  rewritten to check `_generate_candidates()` directly rather than the audit trail's
  text, since collapsing can now legitimately fold `EscalateToHuman` into an unnamed tied
  group with `Stop` — "always considered" is a candidate-generation invariant, not a
  display one. `tests/fixtures/decide_characterization.json` regenerated deliberately
  (2 of 20 cases changed: `at_max_attempts`/`at_cost_cap`, where `Stop` and
  `EscalateToHuman` tie at the `0.0` baseline and are now collapsed into one entry).
  `docs/06-AGENT-SPEC.md`'s "## Candidate generation" section gained a paragraph
  documenting this as expected, common behavior, not an edge case.

### 2. `artifacts/demo_batch.json` was 47 MB committed — audit_text was stored, not derived

Root cause of the bulk of the size (separate from the tie bloat above, which item 1
already fixes): `audit_text` (~11.7 KB of rendered prose per decision) was being computed
once and serialized into the fixture, even though every field it's built from was
*already* being serialized right next to it. Fixed by actually making it derivable rather
than merely asserting it was derivable:

- `agent/audit.py` refactored around a new `RenderFields` dataclass — exactly the scalars
  `render_fields()` (renamed from the module-private renderer) needs, no more, no less.
  `render(record: AuditRecord)` is now a thin adapter (`_fields_from_record` +
  `render_fields`); nothing about `render()`'s own behavior or output changed.
- `api/schemas.py::DecisionOut` gained five small scalar fields
  (`prev_error_source`/`prev_error_step`/`prev_error_reason`/
  `notifications_sent_this_cycle`/`consecutive_failed_cycles`) — the only `DecisionContext`
  fields `render_fields()`'s `SAW` line needs that weren't already on `DecisionOut`.
  Without these, `audit_text` would only have been *approximately* re-derivable, which
  defeats the point.
- `api/converters.py::render_from_decision_out()` — reconstructs a `RenderFields` (and,
  via a new `_action_from_out()`, the original `agent/actions.py` `Action` dataclass) from
  an already-flattened `DecisionOut`, then calls the same `render_fields()` the live path
  uses. Two fields genuinely aren't on `ActionOut` (`ScheduleDebit.notice.template_id`,
  `OfferDateChange.template_id`, `ScheduleDebit.afa_confirmed`) — the two template ids are
  fixed module constants (`agent/compliance.py::TEMPLATE_PDN`/`TEMPLATE_DATE_CHANGE`,
  never a per-decision value), so reproducing them is exact, not approximate;
  `afa_confirmed` is compliance-gate-only and never read by the render path, so a fixed
  placeholder there is genuinely harmless, not a silent inaccuracy.
- `scripts/build_demo_fixture.py` now excludes `audit_text` from every serialized
  `DecisionOut` (`model_dump(exclude=...)`, both top-level and nested inside
  `QueueItemOut.decision`). `api/demo.py`'s fixture loader (`_decision_out_from_json`,
  `_queue_item_from_json`) validates with an empty placeholder, then always overwrites
  `audit_text` with `render_from_decision_out()` — regenerated at read time, every time,
  never trusted from disk even if a stray key were present.
- **Result, combining both fixes**: 45.9 MB → 8.5 MB (~5.4x, not quite the "order of
  magnitude" hoped for). Checked why it stops there rather than going further: mean
  `rejected_alternatives` length per decision dropped from 79.4 to 13.0, and the
  remaining entries are mostly genuinely distinct candidates (different calibration
  steps, different channels) — not further collapsible without hiding real information.
  Judged as a legitimate floor, not a fix left half-done.

### 3. `NaN` in `artifacts/summary.json` was fixed at the wrong layer, corrected

The user caught that the previous session's fix (`web/lib/server-data.ts` regex-replacing
bare `NaN` with `null` before `JSON.parse`) treated the symptom in the one consumer that
happened to crash first, not the producer that emits invalid JSON for *every* consumer —
`/evidence/summary` serves this file verbatim, so any strict JSON parser hitting it
directly (not through this frontend's workaround) would still break. Fixed at the source:
- `eval/run.py::_json_safe()` — new, recursively replaces `float("nan")` with `None`
  before serialization. Several existing rate/mean calculations in `eval/run.py` and
  `eval/metrics.py::bootstrap_mean_ci` already use `nan` as the internal
  "genuinely-undefined" sentinel (e.g. `do_nothing`'s `recovery_rate_of_failed_cycles`,
  undefined because it makes zero attempts, not zero) — left that internal convention
  alone rather than threading `None` through every computation, and sanitize once at the
  serialization boundary instead.
- `main()`'s `json.dumps` call now also passes `allow_nan=False` — a backstop, not the
  primary fix: any `NaN` the sanitizer's recursion doesn't reach now fails loudly with a
  `ValueError` at write time instead of silently reproducing this exact bug again later.
- The already-committed `artifacts/summary.json` was corrected in place by loading it
  with Python's permissive `json.loads` (which tolerates the existing bare `NaN`),
  running it through the same `_json_safe()`, and rewriting with `allow_nan=False` — no
  30-minute `make eval` rerun needed; the underlying computed values are unchanged, only
  the invalid-JSON encoding of "undefined" was.
- `web/lib/server-data.ts`'s regex workaround reverted — a `NaN` reaching that parse now
  is a real regression in the producer, not something to route around again.
- Per the user's instruction, the previously-silent gap is now a stated line in the UI
  rather than an absence: `web/components/ArmComparisonTable.tsx` gained a "Recovery rate
  (of failed cycles)" column (the metric this exact `null` belongs to, and one
  `docs/07-EVAL-SPEC.md` already names — an omission from the first `/evidence` pass, not
  new scope), rendering `null` as `"n/a — no attempts made"` via a new
  `formatCiPctOrNA()`/null-safe `formatCiInr()`/`formatCiCount()` in `lib/format.ts` —
  never `0`, which would misrepresent "not measured" as "measured zero."
  `lib/types.ts::CIValue`'s `point`/`ci_lo`/`ci_hi` are now typed `number | null` to match
  reality, forcing every current and future consumer to handle the null case rather than
  assuming a bare `number`.

`make check` (ruff, mypy, pytest) and `web`'s `tsc --noEmit`/`next lint`/`next build`
(306 pages, all static) all green after all three fixes, including a full fresh
`npm run sync-data` picking up the corrected `summary.json` and the shrunk
`demo_batch.json`. The fixture-loading (non-live) path was specifically re-verified after
item 2's refactor by hiding `data/dobara.sqlite3` and confirming `get_demo_data()` still
returns fully-rendered `audit_text` with correctly-collapsed tie groups.

## [2026-08-27] Pre-registration: the headline rerun, committed before the run starts

**The gap this closes.** `artifacts/summary.json` on disk (30-seed run, 26 Aug,
`elapsed_seconds: 6061.9`) was generated by a `dobara` policy whose tie-break behavior
`184f157` (27 Aug, this same day) changed. The only later touch to `summary.json` was
`fa8204d`'s NaN-serialization fix — not a re-run. Since the tie-break governs which
candidate *date* wins in 76% of decisions, and the simulator's hidden latent-balance
process makes true success probability genuinely date-dependent (the tie was only ever in
the model's calibrated estimate, never in the world), the realized headline can move. This
entry is written, and committed, **before** `make eval`/`make sensitivity` are re-run —
so whatever the new number is, this paragraph is proof the expectation was not
back-fitted to it.

**The commitment, stated in advance:**

1. `agent/decide.py::_tie_break_score` was designed and committed (`184f157`) on
   principle — "when expected value is indifferent, restraint decides," the same
   restraint the motto states everywhere else in this project — **before** anyone knew
   whether it would raise or lower the paired headline. Git's own commit ordering is the
   proof: `184f157` predates this entry and the rerun it triggers.
2. **We keep the principled tie-break whether the headline rises or falls.** The direction
   of the effect is explicitly not a criterion for keeping or reverting the rule.
3. **If the rerun shows a fall — even a headline that turns negative or loses
   significance — we report the fall, plainly, in the same place and with the same
   weight this repo has given every other honest result (the SBI restraint cost, the
   `aggressive_8x` collapse, the `ltv.margin_factor` break-even) — and keep the rule
   anyway.** A tie-break chosen for restraint that happens to also help the number is
   fine to report as a *pleasant confirmation*, stated as such; a tie-break kept only
   because it happened to help the number would be the exact failure mode this
   pre-registration exists to prevent. We do not swap the rule for a better-performing
   one after seeing this result, and we do not re-run with a different tie-break to
   compare.
4. **What would actually change our mind** (stated for completeness, not because it's
   expected): a finding that "closest to declared day, else earliest" is *itself* not the
   most restraint-consistent rule available — e.g. a date-change-offer interaction bug,
   or a case where "earliest" measurably increases rather than decreases customer
   burden. That is a correctness question, separable from whether the headline moved,
   and would be investigated and fixed on its own merits regardless of which direction
   the number goes.

**What we predict, stated honestly as a guess, not a hedge:** most likely a small move,
direction genuinely unknown. The reasoning cuts both ways — "closest to declared
preferred day" is real convergence pressure `DOBARA-CONVERGE` was already designed to
exploit, which argues for a rise; but the previous, unexamined "first in generation
order" pick was itself an accident with no argument for or against it, so there is no
principled basis to predict which direction "correcting" it moves a number this close to
a break-even boundary (₹66/mandate on a base where the sensitivity sweep already showed a
break-even ~33% away). We are not confident enough in either direction to call this
anything but genuinely unmeasured until the rerun completes.

Rerunning `make eval` (30 seeds × 5,000 mandates, ~101 min) and `python -m eval.sensitivity`
next, both now stamped with `provenance.generated_at`/`git_commit`
(`eval/provenance.py`, new) so this exact gap — an evidence artifact silently outliving
the code that produced it — is a `make check` failure from now on
(`scripts/check_artifact_freshness.py`), not a manual audit.

## [2026-08-27] The reconciliation: rerun complete, prediction resolved

`make eval` (30 seeds × 5,000 mandates, `nohup`, 102.8 min) and `python -m eval.sensitivity`
both completed clean, chained automatically so neither was launched by hand at the wrong
moment. Both artifacts are now stamped `provenance.git_commit: 3c38f314ef77...` (the
pre-registration commit) and pass `scripts/check_artifact_freshness.py`.

**The headline moved by −₹0.28/mandate — a rounding-level change, reported at full
weight per the pre-registration, not softened because it happened to be a fall (however
tiny):**

| | Old (26 Aug, pre-tie-break-fix) | New (27 Aug, post-`184f157`) |
|---|---|---|
| Net LTV lift, total (one seed) | ₹329,940.56 [₹269,095.77, ₹403,153.56] | ₹328,533.88 [₹266,525.58, ₹401,362.34] |
| Net LTV lift, per mandate | ₹65.99 [₹53.82, ₹80.63] | ₹65.71 [₹53.31, ₹80.27] |
| Significant | Yes | Yes |

**`eval/sensitivity.json` is essentially bit-identical**: of 30 swept points across all
four axes, 28 are byte-for-byte unchanged; two points on the `date_change_offer.response_rate`
axis moved by ~₹0.00007 (a fraction of a paisa — floating-point-level, not a real effect).
Both break-evens are unchanged: no break-even vs `aggressive_8x` anywhere in [0.05, 0.15];
break-even vs `razorpay_default` still interpolates to hazard ≈ 0.0738 (ratio ≈ 1.91%
against NPCI's 2.5%).

**Why the effect is this small, worth understanding rather than just reporting:** the
tie-break only ever activates *among candidates the calibrator already can't
distinguish* (`docs/DECISIONS.md` [2026-08-27], "the isotonic calibrator is too coarse").
The realized-outcome difference between two dates the calibrated model treats as
identical is bounded by how much the *true*, hidden date-dependent signal actually
differs within that narrow band — and `sim/engine.py`'s `dow_weights` effect, while real,
is modest relative to the dominant drivers of success (bank health, attempt count, amount
band). A large aggregate swing was never the likely outcome of fixing an arbitrary pick
among near-equivalent candidates; a large swing would have been the *surprising* result,
worth distrusting on its own. This is consistent with, not contradicted by, the
individual-decision finding that 76% of decisions had their date determined by the fix —
individually consequential, in aggregate close to a wash, because both the old and new
picks were drawn from the same narrow, model-indistinguishable band.

**The commitment from the pre-registration entry above is honored**: the rule is kept.
The result here is too small a move to have actually tested the resolve the
pre-registration exists to protect — but the process was followed regardless, and the
entry stands as written, not edited after the fact to look more decisive than it needed
to be.

**`/evidence` fixed to compute from `artifacts/summary.json` instead of quoting it.**
Reviewing the page for this reconciliation found the headline, mechanism decomposition
("gross given up" / "mandate value bought back"), and lift-percentage callouts were
**hardcoded from the original README prose** rather than computed from `summary.json` — a
real bug caught by this rerun, not by review: a hardcoded "₹66"/"1.46%"/"₹742,361" would
have silently gone stale exactly the way `summary.json` itself just did, and for the same
reason (no mechanism forcing the two to stay in sync). Fixed to compute from
`summary.arms`/`paired_*` directly; a page-footer note states the before/after rerun
numbers inline and links to this entry. Caught in the same pass:
`revocations_total`/`notifications_total` are mandate *counts*, not rupees — an early fix
routed them through `formatInr()` (prepending ₹ to a count), corrected to
`formatNumber()`. **`README.md` and `docs/07-EVAL-SPEC.md` were not touched this
session** — both still quote the pre-rerun figures (₹65.99 vs the new ₹65.71/mandate, a
difference below the precision either document rounds to); updating them is a follow-up,
not done here.

**A known gap this rerun did not close, flagged rather than left silent**:
`artifacts/money_chart_data.json` also replays `dobara`'s `decide()` (single seed 301,
n=5,000, a per-cycle instrumented loop) and is therefore, by the exact same reasoning as
`summary.json`/`sensitivity.json`, stale relative to `184f157`. It was out of this
session's explicit scope (`make eval` + `make sensitivity` only) and, unlike those two,
was never generated by a committed script — the original replay was a scratch script per
an earlier `docs/DECISIONS.md` entry, not reproducible with a single command. Deliberately
**not** added to `scripts/check_artifact_freshness.py`'s `ARTIFACTS` list yet: doing so
would fail `make check` with no remediation path committed alongside it, which is worse
than a documented, conscious gap. Next session: either write and commit a
`scripts/build_money_chart.py` (closing this gap properly, matching the discipline
`build_demo_fixture.py` already set) or accept the chart as a qualitative/shape
illustration only and say so on `/evidence` — but not leave it silently unstamped.

---

## 2026-08-27 — Visual pass fixes: legends, mandate page, queue restraint, tile scopes, money-chart script

A headless-Chrome visual pass (`--headless --virtual-time-budget=15000
--window-size=1440,5200 --screenshot=... http://localhost:3000/evidence`, run from outside
the extension) found five defects, all fixed this session:

**1. Legend/x-axis collision on `MoneyChart` and `SensitivityChart`.** Recharts'
`<Legend>` defaults to `verticalAlign="bottom"`, which sat directly on top of the `Cycle`
/ `revocation.hazard_per_failure_notification` axis labels and their tick numbers on both
headline charts. Fixed by moving `<Legend verticalAlign="top" align="center" />` above the
plot on both, with matching bottom margin/height bumps so nothing else shifted into its
place.

**2. A second, more serious bug found while verifying the legend fix**: with the legend
fix alone, both charts' `<Line>`s and `ReliabilityChart`'s diagonal reference line still
rendered as blank or barely-drawn paths under headless capture — confirmed via
`--dump-dom`, not just the screenshot: the SVG `<path>`s existed but with
`stroke-dasharray` values like `"5.17px 966px"`, i.e. Recharts' default mount animation
frozen a few pixels into its draw, never completing. Increasing `--virtual-time-budget`
to 25000 did not fix it — this was not the "8s renders blank" budget issue the visual-pass
prompt warned about, but headless Chrome's rAF/compositor not reliably ticking Recharts'
animation to completion. Fixed by setting `isAnimationActive={false}` on every `<Line>`
and `<Scatter>` in `MoneyChart.tsx`, `SensitivityChart.tsx`, and `ReliabilityChart.tsx` —
also makes screenshot-based verification (see below) deterministic instead of racing an
animation.

**3. `/mandate/[id]`'s ~1,700px void and clipped cycle cards.** The void was
`app/layout.tsx`'s sticky-footer pattern (`html.h-full` + `body.min-h-full.flex-col` +
`main.flex-1`): with the 5200px-tall capture window, `main` (and therefore the page)
stretched to fill the full artificial viewport height regardless of actual content,
making any short page look broken. Removed `h-full`/`min-h-full`/`flex-1` from
`layout.tsx` — the footer now sits directly after content instead of being forced to the
bottom of an oversized viewport. Separately, the mandate timeline's 8 cycle cards used
`overflow-x-auto` + `flex min-w-max`, which at n=8 cards (~1408px) exceeded the ~976px
content width and clipped mid-word with no visible scroll cue (compounded by
`--hide-scrollbars` in the capture, but a thin/auto-hidden native scrollbar is easy for a
real user to miss too). Changed to `flex flex-wrap` so cards wrap onto a second row
instead of requiring horizontal scroll at all.

**4. Control Room queue hid the thesis.** `getQueueRows()` (`lib/server-data.ts`) only
ever surfaced each mandate's *first* decision, which is `schedule_debit` for effectively
every row (150/150 in the current fixture) — the STOP/ABSTAIN behavior the product exists
to demonstrate was invisible in the primary view even though the header tile already says
"attempts not made: 44." Added `QueueRow.terminal_action_type` (the `action_type` of each
mandate's *last* audit-trail record, computed server-side from `audit_by_mandate`, which
was already loaded — no new data shipped to the client beyond one string per row) and a
`→ stop`/`→ abstain`/`→ escalate_to_human` badge in `ControlRoomClient.tsx` whenever the
terminal action differs from and is more restrained than the first. Confirmed against the
committed fixture: 12/150 mandates actually end this way. Also made the queue a
`max-h-[720px] overflow-y-auto` region with the Active Case panel `lg:sticky lg:top-20`,
so a long queue no longer leaves a vast empty column beside a short detail card.

**5. `₹ at risk` vs `₹ recovered (gross)` scope mismatch.** `amount_at_risk_inr` is each
mandate's due amount for its *current* cycle only (`api/converters.py`); `gross_recovered_inr`
sums each mandate's recovered amount across *every* cycle it was simulated through (up to
8) — recovered is ~7x at-risk not because of an arithmetic error but because the two
tiles have different denominators. Relabeled to `₹ at risk (this cycle)` / `₹ recovered
(gross, all cycles)` and added a one-line `source` caption on each `StatTile` stating the
scope explicitly, rather than changing the numbers.

**`artifacts/money_chart_data.json` gap (flagged, not fixed, in the entry above) is now
closed.** Added `MandateResult.per_cycle_gross_inr` / `per_cycle_net_inr` to
`eval/runner.py` — a cumulative-to-date snapshot appended after every cycle actually run
in each of the three arm-loop functions (`_run_cadence_arm`, `_run_dobara_arm`,
`_run_oracle_arm`), padded to `n_cycles` by repeating the final value for a
revoked/hard-declined mandate. Purely additive: no existing `MandateResult` field's value
changes, so the 30-seed harness and sensitivity sweep are unaffected (confirmed:
`razorpay_default`'s regenerated series is byte-identical to the pre-existing artifact,
since that arm doesn't call `decide()`; `dobara`'s series shifted by the same
rounding-level amount as the `summary.json` rerun above, for the same tie-break-fix
reason). New `scripts/build_money_chart.py` is the one committed producer, seed 301 (same
seed the old scratch script used), stamps `provenance` via `eval/provenance.py::stamp()`,
and is registered in `Makefile` (`make money-chart`) and
`scripts/check_artifact_freshness.py`'s `ARTIFACTS` list.

All five fixes re-verified with the same headless-Chrome screenshot recipe after the
change (not just reasoned about): legends clear of axes, `/mandate/33`'s 8 cycles wrap
into two rows with its `stop` outcome visible, Control Room tiles show scope captions,
queue is a fixed-height scroll region with a sticky detail panel. `make check` (ruff,
mypy, pytest — 95 passed, `check_artifact_freshness` — all 4 artifacts fresh at
`17762ec13c7d`/`3c38f314ef77`) and the web build (`tsc`, `eslint`, `next build`, 306
static pages) all green.

**Vercel CLI's default per-file upload can hang/loop on this repo** (seen on both
54.9.1 and after upgrading to 59.7.0 — not version-specific). Symptom: `vercel --prod`
spins issuing hundreds of identical `GET /teams/{id}` requests within milliseconds and
eventually fails with `Error: Upload aborted`. Workaround that reliably works:
`vercel --prod --yes --archive=tgz`, which uploads the build as one tarball instead of
per-file. Use `--archive=tgz` as the default invocation for this project going forward,
not just as a fallback after a failure.

**Light mode (`ThemeToggle`) verified against `/evidence`, `/control-room`, and
`/audit/144`'s abstain banner** — the palette was designed dark-first
(`docs/08-FRONTEND-SPEC.md`) and had never actually been rendered in light until this
check. Held up with no fixes needed: five-arm table's highlighted `dobara` row, the
money chart's five arm-colored lines, both calibration scatter plots, red/green
callout numbers, and the warning-toned abstain banner all stayed legible and
distinguishable against the light surface. The `dobara`/`razorpay_default` lines
render very close together on the money chart in both themes — that's the headline's
real (small) margin, not a color-contrast defect.

## [2026-08-28] `/audit` "ask why" box built; free-tier LLM batches are not one provider's problem

Built `llm/provider.py` (`GeminiProvider`, `GroqProvider`, both behind the same
`LLMProvider` protocol per `docs/03-TECH-STACK.md`), `llm/narrate.py` (the prompt --
explain the structured record, never invent or second-guess it), and
`scripts/generate_ask_why.py` (`make ask-why`), which narrates every decision in
`artifacts/demo_batch.json` and caches the result to `artifacts/llm_cache/ask_why.json`,
committed. The frontend (`AskWhyBox.tsx`) reads the cache as a static asset and renders
nothing for a decision it has no entry for -- never a broken empty state. States plainly
in the UI that the narrative was generated ahead of time from the audit record, by a
model that never touched the money decision -- the architecture's central claim, made
visible rather than merely asserted, per the user's explicit instruction.

**Generating the full ~1,300-decision batch took most of an evening and six provider/model
switches**, none of them the same failure twice:

1. `gemini-3.6-flash`: free tier is **20 requests/day**, not per-minute. Exhausted at 19.
2. `gemini-3.5-flash-lite`: fresh bucket, **500 requests/day**. Exhausted at ~499.
3. A first retry-classifier bug: matched the word "billing" to detect unrecoverable
   billing exhaustion, but Google's *every* 429 body contains boilerplate mentioning
   billing -- false-positive-aborted a real, retryable RPM=15 limit. Fixed to require the
   exact phrase "prepayment credits are depleted".
4. `gemini-3.1-flash-lite`: another fresh 500/day bucket. Exhausted at ~494 more.
5. `gemini-3-flash-preview`: fresh, but shares the *full* "flash" tier's 20/day bucket,
   not the lite tier's 500/day -- exhausted after 13.
6. A false "reset" sighting: past UTC midnight, one smoke-test call to
   `gemini-3.5-flash-lite` returned 200, read as the daily quota clearing. It was a
   one-off; the very next real call in the batch still 429'd. Don't trust a single
   probe to mean a quota window reset -- confirm with the batch itself.
7. Switched provider entirely to **Groq** (`docs/03-TECH-STACK.md` had already named it
   as an anticipated swap target). `openai/gpt-oss-20b`: fast (~1s/call), good quality,
   but its 429 body said "tokens per day (TPD)" -- Gemini-specific non-retryable
   detection (`"perday"` in a `quotaId` field) didn't catch Groq's prose shape, and the
   generic `retry-after` header (75s) looked like an ordinary short rate limit. It
   wasn't: the script spent ~7 minutes stuck retrying a 200k/200k TPD ceiling that
   wasn't going to clear. Fixed by adding Groq's phrasing ("tokens per day", "requests
   per day") to the non-retryable marker list.
8. `openai/gpt-oss-120b`: separate fresh TPD bucket, exhausted after ~130 more (each
   model's TPD budget is independent, confirmed by trying several before finding one
   with headroom -- `groq/compound-mini` turned out to internally route through
   `gpt-oss-120b` and shared its exhausted bucket).
9. `qwen/qwen3.6-27b`: fresh bucket, but emitted a visible `<think>...</think>` reasoning
   block before the actual answer, unprompted -- would have corrupted the cache with a
   chain-of-thought dump instead of a short narrative. Not used; `llm/narrate.py` now
   strips `<think>` blocks defensively regardless of model, so a future swap that
   reintroduces this doesn't require catching it by eye.
10. `qwen/qwen3.8-27b`: fresh bucket, no thinking output, finished the remaining 37.

**Result**: 1,296/1,296 decisions narrated, 0 failures, `<think>`-block sweep confirms
none leaked into the committed cache. Every model switch was verified against a real
audit record (an abstain case and a schedule_debit case) for narrative quality and
faithfulness before being adopted, not assumed.

**Also fixed while here**: `scripts/check_artifact_freshness.py`'s `main()` used
`all(check_one(...) for ...)`, which short-circuits on the first `False` -- a real,
pre-existing `summary.json` staleness (from commit `1c6286f`, unrelated to this work)
meant the script silently never even checked whether the newly added `ask_why.json` was
fresh. Changed to a list comprehension so every artifact is always checked and reported.
Running it after the fix surfaced that staleness for the first time: `summary.json`,
`sensitivity.json`, `demo_batch.json`, and `money_chart_data.json` all predate `1c6286f`,
which touched `eval/runner.py`'s per-cycle tracking -- **not fixed here**, out of scope
for tonight's ask-why work and requires a full `make eval` rerun (~100 minutes for the
30-seed harness). `artifacts/llm_cache/ask_why.json` itself reports fresh.

## [2026-08-28] Per-entry ask-why provenance, not file-level

**Chose**: `llm/provider.py` and `scripts/generate_ask_why.py` stamp
`{text, provider, model, generated_at}` on every individual cache entry in
`artifacts/llm_cache/ask_why.json`, not once at the top of the file.

**Why**: the cache's provenance is genuinely heterogeneous -- the free-tier quota saga
documented the same day (`GeminiProvider` across three sub-models, then `GroqProvider`
across three more) means different entries in the *same committed file* were narrated by
different providers and models at different times, entirely dependent on which quota
bucket happened to have headroom when that entry's turn came up. A single file-level
stamp would misrepresent every entry as sharing one provenance. This repo already holds
every other kind of output to per-record provenance -- `model_version` on every audit
record, a `source` field on every simulator parameter and every UI number -- so the
narratives were the one place still cutting that corner. Per-entry stamping also means a
future partial regeneration (only the entries a grounding-check triage flags, as
happened same-session in `40b4a12`) doesn't retroactively mislabel the untouched
majority's provenance.

**How to apply**: any future cache or artifact holding multiple independently-generated
records should default to per-record provenance, not per-file, unless every record in
the file is genuinely known to share one generation event.

## [2026-08-28] Numeric grounding checker design + the 8 whitelisted false positives

**Chose**: `scripts/check_ask_why_grounding.py`, wired into `make check`, extracts every
numeric token from each cached ask-why narrative and asserts it traces back to a number
actually present in that decision's rendered audit record (via
`api/converters.py::render_from_decision_out`), tolerating documented format
equivalences only (rounding to 0/1/2 decimal places, probability-as-percentage). Anything
outside those tolerances is flagged for human triage, never silently passed or silently
dropped.

**Why**: this is the concrete mechanism behind CLAUDE.md's "money decisions never pass
through an LLM" -- the LLM narrates a decision it never made, and this checker is what
makes "narrates faithfully" a testable claim rather than a hope. A narrative inventing a
number (a compliance-clause count, a candidate count, a rupee figure) would otherwise
only be caught by luck during a hand-read.

Eight entries were individually whitelisted after the full 1,296-narrative run, each
reviewed against its own audit record before being added (never by loosening the
matcher's tolerance):

- **Three entries citing RBI-PDN-24H** (`18:5:1`, `78:2:1`, `112:7:1`, token `24.0`):
  the narrative names "the 24-hour rule" by its regulatory content, not as a fabricated
  count -- the number is the clause's real cited duration, just not printed as a raw
  digit anywhere in the record's structured fields the extractor reads.
- **Three entries citing RBI-AFA-15K** (`83:8:1`, `96:5:1`, `40:8:3`, token `15000.0`):
  same pattern for the ₹15,000 additional-factor-authentication threshold named by rule,
  not restated as a bare number in the record.
- **`103:5:2`** (token `13.92`): the record's 95% CI lower bound is -₹13.92; the
  narrative correctly restates this as "losing ₹13.92" -- the sign is carried by the
  word "losing" rather than a literal minus sign in the narrative's own digits, so the
  checker's sign-preserving comparison doesn't match it against the negative ground
  truth. Verified by hand that the underlying claim is accurate before whitelisting.
- **`24:6:1`** (token `900.0`): the record's largest rejected-alternative delta is
  exactly ₹909.45 below the chosen candidate; the narrative paraphrases this loosely as
  "up to over ₹900" rather than the exact figure. Directionally and numerically
  consistent with the record -- a loose paraphrase, not an invented number -- just not
  an exact-token match the extractor can credit automatically.

**How to apply**: any new grounding-checker flag should get the same treatment --
read the specific narrative against its specific audit record, and only whitelist (with
a comment naming the case and the reasoning) if the underlying claim is verified
accurate. A flag that turns out to be a real hallucination gets regenerated, not
whitelisted; 14 of the 22 flags in the full-corpus run were exactly that (see the
sibling `40b4a12` entry below).

## [2026-08-28] CI scope gap: mypy, artifact freshness, and no web build job

**Found**: `.github/workflows/ci.yml` had drifted from `make check` and from what
Vercel actually builds. Specifically: the `mypy` step's package list was missing
`eval`, `api`, `llm`, and `scripts` (only checking `agent models sim features`, the
Phase 0-3 set, never updated as later phases added packages); there was no
artifact-freshness gate, so a landed code change that silently staled a committed
`artifacts/*.json` (exactly the class of bug `check_artifact_freshness.py` exists to
catch, per the `[2026-08-27]` "headline evidence rerun" entry) would pass CI; and there
was no job building `web/` at all -- `tsc`, `eslint`, and `next build` were only ever
run by hand, locally, before a commit.

**Why this matters**: the missing web build job was not a theoretical gap -- verified
by actually running each CI step locally rather than trusting the YAML, which caught a
real, pre-existing lint error in `ThemeToggle.tsx` (a legitimate SSR-hydration pattern
the newer `react-hooks` lint rule flags) that had been shipping unnoticed because
nothing in CI would ever have caught it. A judge reading this repo's CI badge as "this
build is verified" was being told something false for the frontend half of the
submission.

**Fixed**: mypy's invocation now matches `make check`'s full package list; the
artifact-freshness check runs as its own CI step (requires `fetch-depth: 0` on checkout
-- the freshness script walks `git log <artifact's commit>..HEAD`, which a shallow
depth-1 checkout can't do); a second CI job builds `web/` (`tsc --noEmit`, `next lint`,
`next build`, static export) on every push/PR, the same build Vercel runs on deploy.

**How to apply**: when adding a new top-level package or a new deployable surface
(frontend, a second service, etc.), update `.github/workflows/ci.yml` in the same
commit, not as a follow-up -- this gap sat unnoticed for multiple phases specifically
because it wasn't.

## [2026-08-28] Stale-artifact rerun + full-corpus grounding triage

Full regeneration chain (`make demo-fixture` -> `eval` -> `sensitivity` ->
`money-chart`), triggered by the `[2026-08-28]` CI-scope entry's discovery that
`summary.json`/`sensitivity.json`/`demo_batch.json`/`money_chart_data.json` all
predated commit `1c6286f`'s additive per-cycle tracking change in `eval/runner.py`.

Confirmed empirically, not just by code-diff, that the rerun was safe to treat as a
non-event for the narrative cache: `demo_batch.json`'s decision content (chosen action,
rupee math, rejected alternatives, clauses -- every field, all 150 mandates) is
byte-identical before and after. Because of that, the 1,296 already-cached narratives
stayed valid and were **not** regenerated wholesale -- zero additional LLM quota spent
on the ~1,282 unaffected entries. Every headline number already quoted in `README.md`
(the ₹65.71/mandate paired comparison, all five arms' gross/net/attempts/notifications/
revocations) is also byte-identical to the pre-rerun figures; no README changes were
needed.

Ran `scripts/check_ask_why_grounding.py` against the complete 1,296-narrative corpus for
the first time (previously only spot-checked against a 50-entry sample). 22 flagged,
triaged individually:

- **14 real hallucinations**, regenerated and reread clean: a fabricated "N compliance
  checks" count invented in ten narratives (the record always satisfies exactly 15
  named clauses, never counted as a bare number); one wildly wrong candidate-count claim
  ("90 other options" against a record with 5 total candidates); one garbled date
  fragment ("Fe20"); one decimal-comma typo ("₹566,44" for ₹566.44); one off-by-one
  alternative count.
- **8 checker false positives**, whitelisted with individual reasoning -- see the
  sibling `[2026-08-28]` "Numeric grounding checker design" entry above for the full
  per-case breakdown.

Grounding check is now clean across the full corpus: 0 flagged, 0 unmatched tokens.

**Also caught by a separate hand-read of ten narratives** (not driven by the automated
checker, which structurally can't catch a narrative describing the *wrong action* when
every number it states is individually accurate): `5:2:2`'s STOP-decision narrative
claimed the system "escalated the case for manual review," but the actual decision was
STOP with no escalation -- the model appears to have mistaken a rejected `EscalateToHuman`
alternative (tied at the same E[net] as the chosen STOP) for the action actually taken.
Regenerated; the new narrative correctly describes only the stop.

**How to apply**: the grounding checker verifies numbers, not actions -- a hand-read
pass against a small sample stays necessary even with the automated gate in place,
specifically for the class of error where every digit is right but the described action
isn't. `make check` (95 tests, artifact freshness, ask-why grounding) and the web build
(306 static pages) green throughout.

## [2026-08-28] Redesign Session B: shadcn init overwrote project tokens, corrected by hand

**Found**: `npx shadcn@latest init -d` (non-interactive, as `docs/10-REDESIGN.md` §3.5
explicitly warned against letting happen) rewrote `app/globals.css`'s `--border` token
from `rgba(11, 11, 11, 0.1)` to a hardcoded `oklch(0.922 0 0)`, and appended a full
second color system keyed off a `.dark` class selector (`--background`, `--card`,
`--primary`, etc., each redefined again under `.dark`) alongside the project's existing
`:root` / `prefers-color-scheme` / `[data-theme="dark"]` layering. Left in place, this
would have given the project two independent, unsynchronized theme systems — shadcn
primitives would render one palette, hand-rolled components another, and the light-mode
verification already done in `docs/DECISIONS.md`'s `[2026-08-27]` entry would no longer
cover shadcn-rendered surfaces at all.

**Fixed**: reverted `globals.css` to the pre-init version, then added a small,
by-hand "shadcn/ui token bridge" block: every variable name shadcn's generated
components expect (`--background`, `--foreground`, `--card`, `--popover`, `--primary`,
`--secondary`, `--muted`, `--accent`, `--destructive`, `--input`, `--ring`) is defined
once, as a `var()` reference to the project's own existing tokens (`--surface-0`,
`--text-primary`, `--arm-dobara`, `--status-critical`, …). Because those underlying
tokens already re-resolve across `:root` / `prefers-color-scheme` / `[data-theme]`, the
bridge needs no `.dark`-class duplication of its own — a shadcn `Tooltip` or `Table`
now inherits the exact same light/dark behavior as every hand-rolled component, by
construction, not by a second maintained copy.

**Why this matters beyond this one init run**: `docs/10-REDESIGN.md` names the risk
explicitly ("shadcn init MUST point at the existing tokens ... do not let it overwrite
the palette") because a CLI init is not idempotent-safe against a project with its own
already-designed token system — it assumes it owns `globals.css`. Any future `npx
shadcn add <component>` is safe (it only adds a new file under `components/ui/`), but
another `shadcn init` (or an `--overwrite` on an existing primitive) would need the same
by-hand check against `globals.css` before trusting its diff.

**How to apply**: when a future session runs any shadcn CLI command that touches
`globals.css`, diff it before accepting — the CLI's default behavior is to install its
own palette, not detect and preserve an existing one, regardless of how the token names
happen to collide.

## [2026-08-28] Redesign Session B: StatTile's CI/source rule stays a convention, not a hard gate

**Considered**: making `StatTile` throw when rendered with neither `ciText` nor
`source`, to give CLAUDE.md's "every number reported must have a confidence interval
and a stated source" a structural enforcement point, the same way
`tests/test_no_llm_in_money_path.py` structurally enforces the LLM-boundary rule.

**Rejected, for now**: three live call sites in `components/control-room/
ControlRoomClient.tsx` (`Notifications sent`, and two others) are live fixture counters
with no meaningful statistical CI — they're exact counts from the demo population, not
point estimates with uncertainty. A hard throw at those call sites would break the
build over a case the rule was never meant to catch, and Session B's charter is
foundations that don't break anything, not a stricter reinterpretation of an existing
CLAUDE.md rule made unilaterally mid-session.

**Left as**: a docstring on `StatTile` documenting the rule and naming live-counter
values as the one legitimate no-CI exception (which still needs a `source`), with
enforcement deferred to whichever session actually touches those three call sites (most
likely Session D, `/control-room`) — at which point the source field on all three should
be added and, at that point, revisit whether a structural gate is worth adding.

## [2026-08-28] Redesign Session B: `make check` red for a pre-existing, unrelated reason

Session B touched only `web/` — confirmed via `git status`/`git diff` scoping before
committing, no Python file changed. `make check` nonetheless fails at the very last
step, `check_artifact_freshness.py`, on `artifacts/llm_cache/ask_why.json`: its
top-level `provenance.git_commit` stamp is `f199e87`, but the immediately following
commit, `40b4a12` (the stale-artifact rerun two sessions before this one), touched
`artifacts/demo_batch.json` — a path the ask-why cache's freshness check watches,
per the `[2026-08-28]` "grounding checker design" entry's sibling work. `40b4a12`'s own
commit message confirms the touch was content-neutral (decision content byte-identical
before/after), but `check_artifact_freshness.py` has no mechanism to know that — it
fails on any post-stamp touch to a watched path, unconditionally, which is exactly its
documented design (see the module docstring: "the check only fails on the case it
exists to catch: real, landed commits ... since the artifact was generated" — it cannot
distinguish a landed-but-inconsequential commit from a landed-and-consequential one
without re-deriving the content diff itself).

**Not fixed here**: two real options exist — (1) rerun `make ask-why` to bump the
stamp, which costs LLM quota (per the `[2026-08-28]` "ask why box built" entry's
six-provider quota saga) for zero actual content change, or (2) teach the checker to
compare content hashes rather than just commit ancestry for this one artifact, which is
a real design change to a script every other artifact also depends on. Both are
judgment calls belonging to whichever session next does Python/`eval/` work, not a
side effect of a frontend foundations session. Flagged in `PROGRESS.md`'s `##
CURRENT STATE` rather than silently worked around.

## [2026-08-28] Post-Session-B follow-ups: artifact-freshness gate fixed, base-nova deviation recorded

Three small follow-ups to `da1bd22` (Session B), before Session C.

**1. Fixed the artifact-freshness gate's structural false positive on the ask-why cache.**

Confirmed the mechanism exactly as the entry above predicted: `eval/provenance.py::stamp()`
records `git_commit` as the commit current at *write time*, which is necessarily the
**parent** of the commit that actually lands the write. So any commit that regenerates
`artifacts/demo_batch.json` — even byte-identically — stamps `artifacts/llm_cache/
ask_why.json`'s dependency check with its own parent and then fails the ancestry check
against itself. The gate could never be satisfied from inside such a commit; it required
a separate follow-up commit purely to bump the stamp. `40b4a12` hit exactly this and
could not have avoided it.

**Fix, not a workaround**: rather than just rerunning `make ask-why` to bump the stamp
(real option (1) from the prior entry — correct but wastes LLM quota for zero content
change) or leaving ancestry as the only check, added `eval/provenance.py::content_hash()`
— a SHA-256 of the canonical JSON encoding of whatever field is actually consumed
downstream — and changed `scripts/check_artifact_freshness.py` so the ask-why cache's
dependency on `demo_batch.json` is no longer a git-log/ancestry check at all. It is now a
direct content-hash comparison (`HASH_DEPENDENCIES` list): `generate_ask_why.py::
save_cache()` stamps `provenance.demo_batch_content_hash` with a hash of
`demo_batch.json`'s `audit_by_mandate` field (the only field the narration code actually
reads — confirmed via `scripts/generate_ask_why.py` and `api/demo.py::
_decision_out_from_json`) at generation time; the checker recomputes that hash against
the live `demo_batch.json` on every run and only fails if the *content* actually
diverged. `llm/` and `scripts/generate_ask_why.py` stay on the git-log/ancestry check —
a real code change there should still stale the cache.

This is a general design, not a one-off patch: `HASH_DEPENDENCIES` is a list precisely so
a future cached-artifact-derived-from-another-artifact dependency doesn't hit the same
self-inflicted-staleness bug and doesn't need this same investigation repeated.

Restamped `artifacts/llm_cache/ask_why.json`'s `provenance` (git_commit +
demo_batch_content_hash) to current HEAD in this commit, with no narrative content
changed — the 1,296 narratives are untouched, per the prior entry's finding that
`demo_batch.json`'s decision content is byte-identical across `40b4a12`'s rerun.

**Also recording**: this gate was already red as of `40b4a12` (its own commit, by
construction, per the mechanism above) — meaning `40b4a12`'s commit message claim of a
clean `make check` was not accurate at the time it landed. The rest of that commit's
claims (byte-identical decision content, unchanged README figures, the 22-narrative
grounding triage) were independently verified in this session and stand; only the
"`make check` passes end-to-end" framing was wrong, and it was wrong for the structural
reason above, not because of any actual regression `40b4a12` introduced.

**2. Documented an undocumented spec deviation**: `web/components.json` ships
`"style": "base-nova"`; `docs/10-REDESIGN.md` §3.5 specified `"new-york"`. Session B's
diff summary already explained this was a deliberate choice — `base-nova` is the current
shadcn CLI default and is designed to pair with `@base-ui/react` — but the deviation was
never written back into the spec or logged here, so it read as spec drift rather than a
decision. Kept `base-nova` (no reason to fight the current default); §3.5 now names it
explicitly and points here for the why.

**3. Left a marker for Session D**, not implemented now: `docs/10-REDESIGN.md` §4
`/control-room` now notes that when the counter call sites in `ControlRoomClient.tsx`
get touched, `StatTile`'s CI/source rule (see the "stays a convention, not a hard gate"
entry above) should move from a documented convention to a type-level requirement —
`source` required, and a `noCi: "reason"` opt-out required in place of a silently absent
`ciText` — rather than a runtime throw, which was correctly rejected in that entry for
breaking the three legitimate no-CI live counters.

## [2026-08-28] Artifact-freshness gate: fix the class, not the instance

`bfa52dc` ("Post-Session-B follow-ups") fixed `artifacts/llm_cache/ask_why.json`'s
structural false positive with a content-hash check, and reported `make check` green.
That report was measured pre-commit, against the working tree — `check_artifact_freshness.py`
is git-log-based, so it could not yet see the commit it was about to become part of.
Verified post-commit (`git log --oneline -1` confirming HEAD was `bfa52dc`, then rerunning
the gate), `make check` was red with **5** failures, not the 1 it started with:
`summary.json`, `sensitivity.json`, `demo_batch.json`, `money_chart_data.json`, and
`ask_why.json`'s ancestry check (separately from its now-passing content-hash check) all
failed. Cause: `bfa52dc` added `eval/provenance.py::content_hash()`, and `eval/` is in
`WATCHED_PATHS` — the very commit that fixed the gate tripped it on every other artifact,
by the same mechanism already diagnosed (path-touched is a bad proxy for
content-could-have-changed) but not yet fixed as a class. A helper function consumed only
by a checker script and by one generator's cache-write path cannot alter any of these five
artifacts' content, yet it staled all of them.

**Fix, generalized this time.** `scripts/check_artifact_freshness.py::stale_commits_for()`
now applies two narrowings to the ancestry proxy, in order, for every commit that touched
a watched path since an artifact's stamp:

1. **Self-regeneration exclusion (automatic).** A commit that rewrites the artifact file
   itself can't be stale relative to itself — `stamp()` records HEAD's parent, so any
   write-commit necessarily post-dates its own stamp. This is the general form of the
   `ask_why.json`/`demo_batch.json` bug from the prior entry, now applied to every artifact,
   not hand-fixed per dependency.
2. **Committed waivers** (`docs/artifact_freshness_waivers.json`): a `(artifact, commit)`
   pair with a written reason, for a commit that touched a watched path but is known not
   to affect that artifact's generation. Added five entries for `bfa52dc`'s `content_hash()`
   addition, each with the specific grep/import-graph reasoning for why that artifact's
   generator doesn't call it. Default stays fail — an unwaived, non-self-regen touch to a
   watched path still fails, which is what must keep catching a real change to
   `agent/decide.py`'s scoring.

Considered but rejected: rerunning `make eval`/`sensitivity`/`demo-fixture`/`money-chart`
to bump stamps with byte-identical content (the "automatic, no judgment" option from the
prior entry) — correct in principle, but `demo_batch.json`'s rerun costs ~100 LLM-quota
minutes for a change that provably touches zero generator code paths; not a good use of
remaining build time for a helper function. The waiver file is the honest version of that
judgment call: written down, attributed to a commit, and inert-by-construction (it doesn't
touch `WATCHED_PATHS` scope, so it can't quietly narrow what the gate catches for anyone
else's real change).

**Test added**: `tests/test_check_artifact_freshness.py` builds a throwaway git repo (never
touches this repo's own history) and exercises `stale_commits_for()` directly: a real
`agent/decide.py`-style change is still flagged stale; a commit that rewrites the artifact
itself is not; a waived commit is reported as waived, not real-stale. This is the gate's
first test of its own correctness.

**Also**: moved `check_artifact_freshness` ahead of `pytest` in `make check` — it's a
git-log query, not a full test run, and previously a stale artifact only surfaced after a
~225s pytest wait.

**Process note, recorded for future gates shaped like this one**: any check that reads
committed git history is structurally blind to the commit it's about to become part of when
run against a dirty working tree. From now on this gate — and any future one with the same
shape — is verified **after** committing, immediately before pushing, not before. See
`PROGRESS.md`'s `## CURRENT STATE` for the same note added to the session protocol.

## [2026-08-28] The landing page's demonstration is generated, not authored
**Chose:** Add an opt-in per-beat trace to the eval harness (`eval/runner.py::AttemptEvent`,
`run_arm(..., trace=True)`) and a producer script, `scripts/build_home_demo.py`, that
replays **one real mandate under two arms** and writes `artifacts/home_demo.json`. The
`/` demonstration renders that file.
**Over:** Hand-authoring the eight-notification sequence in the React component from the
aggregate numbers already committed (`MandateResult` knows *how many* notifications an arm
sent, not *when*), or driving it from `demo_batch.json`, which contains only the `dobara`
arm's decisions and so cannot show the other lane at all.
**Because:** The single most persuasive element on the site would otherwise be the one
element on the site whose numbers nobody could check — CLAUDE.md's "simulated data must be
declared loudly" and "every number reported must have a stated source" apply hardest to
the thing a judge remembers. The trace is default-`False` and threaded explicitly (no
global state), so the 30-seed harness and the sensitivity sweep allocate nothing and behave
identically; `tests/test_runner_trace.py` pins that — it compares traced and untraced runs
field-by-field via `dataclasses.replace(r, events=[])`, so any field added to
`MandateResult` later is covered automatically, and separately asserts the beats
reconstruct the aggregates they accompany.

## [2026-08-28] The demonstration shows the median case, not the best one
**Chose:** Among mandates that revoked under `aggressive_8x` and survived under `dobara`,
select the **median** by dobara's net-LTV advantage on that mandate, and publish the
candidate set's size and the p25/median/p75 of that advantage alongside it on the page.
**Over:** The maximum (most dramatic) case; or an unranked "first qualifying" pick.
**Because:** A worked example chosen because it flatters the thesis is an anecdote; the
median of a stated population, with the spread shown, is a claim a reader can check —
and the page says so in as many words.
**Recorded because the first attempt was wrong in an instructive way:** the initial
criterion ranked by *notifications sent before revocation*, which selected a mandate that
revoked in the **final** cycle of the horizon — the point at which almost no lifetime value
remains to forgo, so the aggressive lane actually netted *more* on that mandate
(₹5,717 vs ₹4,539). Entirely real, entirely honest, and exactly the wrong number to build
a headline on: the ranking optimised for the visual (a long row of notifications) rather
than for the quantity the thesis is about. The fix was to rank by the thesis's own
objective.

## [2026-08-28] `/architecture` reads the compliance rule registry, it does not restate it
**Chose:** `scripts/build_compliance_rules.py` exports `agent/compliance.py::RULES` to
`artifacts/compliance_rules.json` (id, text, severity, citation, source_url, plus the
HARD/SOFT counts), watched by `scripts/check_artifact_freshness.py` like every other
artifact; the page renders that file.
**Over:** A hand-written copy of the rule list in the frontend.
**Because:** A second copy of the rules is a second source of truth, and it goes stale the
first time a rule's text or severity changes — the same failure mode
`money_chart_data.json` had before it got a committed producer ([2026-08-27]). This
generator is model-free and takes seconds, so there is no cost to regenerating it on every
`agent/compliance.py` change.

## [2026-08-28] Compliance gate panel scoped to what's actually serialized
**Chose:** `/control-room`'s per-case compliance gate panel (docs/10-REDESIGN.md §4)
reports candidate count (from `rejected_alternatives`, same source `DecisionCard`
already uses) and the chosen action's own `clauses_satisfied`/`clauses_blocked` —
nothing else.
**Over:** A "which HARD rules eliminated which candidates" breakdown, as §4's prose
literally asks for.
**Because:** `agent/decide.py::decide()` filters candidates against every HARD rule
before scoring (`legal = [a for a in candidates if is_hard_compliant(...)]`) but never
records *which* rule eliminated *which* candidate — only the survivors are scored, and
`clauses_satisfied`/`clauses_blocked` are computed once, against the winning action only.
Inventing a per-rule elimination count would violate CLAUDE.md's "no hand-typed numbers"
rule as surely as a literal `66` in JSX. The panel says so explicitly and points to
`/architecture`'s `ComplianceGateSequence` for the qualitative "In / Gate / Out" picture.

## [2026-08-28] StatTile's CI opt-out is a discriminated union, not a second optional prop
**Chose:** `StatTile` takes `source: string` (required) plus exactly one of `ciText:
string` or `noCi: string`, enforced via a TS union type, not two independent optional
props.
**Over:** Keeping `ciText?` optional and adding `noCi?` beside it.
**Because:** Two independent optionals let a call site omit both silently — exactly the
gap docs/10-REDESIGN.md §4 asked Session D to close. The union makes "no CI" a decision
the caller states, not an omission the compiler lets slide.

## [2026-08-28] Chart mount gates a draw-on-enter reveal instead of retriggering Recharts animation
**Chose:** A `ChartReveal` wrapper (`useInView(..., { once: true })` from `motion`) defers
mounting a chart until it scrolls into view; Recharts' own existing
`isAnimationActive={!isStatic}` mount animation then does the "draw" once the chart
exists. A `?static=1`/reduced-motion pass mounts immediately, skipping the gate entirely.
**Over:** Re-triggering Recharts' animation via a key change or an imperative replay API
on each scroll-into-view.
**Because:** Recharts has no supported "replay this animation" call — the only clean way
to get a draw-on-enter is to control *mounting*, which naturally fires once and never
re-fires on scroll-up (an unmounted-then-remounted chart would re-draw every time,
exactly what §5 rules out). This also sidesteps re-introducing the frozen-mid-draw
screenshot bug: the static branch never depends on scroll position at all.

## [2026-08-28] Session E also fixed a latent bug flagged at session start, not just built new work
**Chose:** `MoneyChart`/`ReliabilityChart`/`SensitivityChart` now call
`useStaticRender()` instead of reading the `staticRender` module const directly during
render.
**Over:** Leaving it as `staticRender`, since Recharts is a client-only render path and
the direct const read caused no visible bug today.
**Because:** The user's session-start review named this as the same latent bug class
Session C's `Demonstration.tsx` hydration mismatch was — reading a `window`-derived const
during render disagrees between server and client markup for any component that *could*
render during SSR, and there was no guarantee a future edit wouldn't make these chart
components reachable from a server-rendered path. `lib/motion.ts`'s hook exists
specifically so this pattern doesn't get re-derived a fourth time; using it here closes
the gap instead of leaving it for Session F or later to rediscover.

## [2026-08-28] Session F discovered `audit_text` was never actually in the committed fixture
**Chose:** Removed `audit_text: string` from `web/lib/types.ts`'s `DecisionOut`, added the
five `prev_error_*`/`notifications_sent_this_cycle`/`consecutive_failed_cycles` fields
that ARE present, and reconstructed the SAW/DID/WHY narrative lines in TypeScript
(`web/components/audit/renderAuditSections.ts`), mirroring `agent/audit.py::render_fields`
term for term from those structured fields.
**Over:** Continuing to read `decision.audit_text` as the old `DecisionCard` did.
**Because:** `scripts/build_demo_fixture.py` deliberately excludes `audit_text` from the
committed fixture (`api/converters.py`: it's an 11.7KB rendered string per decision,
losslessly re-derivable, and only the live `/demo` API path re-renders it via
`api/demo.py::render_from_decision_out`). The static site has no Python runtime at
request time, so `decision.audit_text` was silently `undefined` in every DecisionCard
ever rendered on the deployed site -- caught while wiring Session F's SAW/THOUGHT/ALT/
GATE/DID/WHY grid, which is exactly the kind of defect a stack of `<pre>` paragraphs
hides and a labelled grid surfaces (nothing rendered there before either, just silently).

## [2026-08-28] Contrast fixes are separate CSS variables, not retuned base colours
**Chose:** Added `--arm-dobara-text`, `--status-warning-text`, `--status-critical-text`
(and wired the previously-orphaned `--status-good-text`, defined since an earlier session
but never registered in the `@theme` block, so `text-status-good-text` never existed as a
utility) as darkened/brightened variants used only where these colours render as running
TEXT. Left `--arm-dobara`/`--status-good`/`--status-warning`/`--status-critical` (the
values used for swatches, chart lines, dot fills, badge backgrounds) untouched.
**Over:** Darkening the base tokens directly, which would also be simpler (no new
variables, no ~40 call-site class renames).
**Because:** docs/10-REDESIGN.md §2 locks arm colours to their `references/palette.md`
slots for identity reasons (chart lines, legends, swatches must stay recognizable across
sessions and screenshots); status colours aren't arm colours but are still load-bearing
identity (a green dot means "compliant" everywhere in the UI). WCAG's 4.5:1 floor applies
to text, not to a 2.5mm dot or a 15%-opacity badge fill (which only needs 3:1 as a UI
component boundary and already clears it) -- so the actual defect was narrower than "this
colour is wrong," and fixing only the text contexts avoids re-tuning marks that were
already screenshot-verified and fine. Measured, real failures (light unless noted):
text-muted 3.41:1 -> 5.15:1, status-warning 1.79:1 -> 5.77:1, arm-dobara 4.30:1 -> 6.12:1,
dark status-critical 3.62:1 -> 5.22:1. All others measured and already passing.
