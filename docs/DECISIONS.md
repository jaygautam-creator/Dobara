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
