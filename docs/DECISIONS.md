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
