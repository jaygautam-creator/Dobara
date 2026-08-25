# PROGRESS — Dobara

> **This file is the source of truth for session handoff.**
> Every session: read `## CURRENT STATE` first. Every session: rewrite it before finishing.

---

## CURRENT STATE

**Last updated:** 2026-08-25 (Day 5-6 session)
**Phase:** Phase 0-3 complete. **Phase 4 (evaluation — the gate) IN PROGRESS, not done.**
The harness exists and runs end-to-end (`eval/world.py`, `eval/rng.py`, `eval/arms.py`,
`eval/runner.py`, `eval/metrics.py`, `eval/sensitivity.py`, `eval/run.py`), `agent/decide.py`
was batch-score-optimized (~26x) with a characterization test locking in behavior-identity,
a real bug in the `oracle` arm was found and fixed (it now weakly dominates every arm, as
an oracle must), and a real `P(revoke)` conditional/unconditional-probability bug in
`agent/decide.py`'s `E[net]` formula was found, user-approved, and fixed (see
`docs/DECISIONS.md` [2026-08-25], the two most recent entries). **But Phase 4 is still not
done: the `dobara`-underperforms-`do_nothing` puzzle is NOT resolved by the P(revoke) fix**
— smoke-tested post-fix at n=4,000 (5 seeds): `dobara` now clearly beats
`razorpay_default` (+₹137/mandate net LTV) but still trails `do_nothing` (-₹167/mandate),
and the fix actually made `dobara` retry *slightly more*, not less, which is the wrong
direction to close that specific gap. The full 30-seed harness has **not been rerun** —
relaunching now would just re-spend ~2h reproducing the same open question rather than
answering it; the next investigation should compare the hazard model's predictions at the
*actual* feature values `eval/runner.py::_run_dobara_arm` presents against
`sim.engine.revocation_hazard`'s true values for those same contexts (the previous
session's calibration probe used a small, unmatched synthetic sample). **The current
`artifacts/results.parquet`/`summary.json` predate BOTH fixes (oracle and P(revoke)) and
must NOT be treated as final or quoted anywhere (README, UI, video).** Do not tick Phase 4
checkboxes below based on these artifacts, and do not rerun the full harness until the
`dobara`-vs-`do_nothing` question has an actual answer, not just a hoped-for one.

**Phase 3 done (this session), on top of Phase 0-2:**
- Closed `Action` type (`agent/actions.py`): `ScheduleDebit`/`SendPreDebitNotice`/
  `OfferDateChange`/`EscalateToHuman`/`Stop`/`Abstain` as frozen dataclasses. A bare
  debit-without-notice is structurally unrepresentable — `ScheduleDebit` requires a
  `notice` field — rather than relying on a predicate that could be forgotten.
- `agent/stopping.py`: the seven named stopping reasons, all reachable and unit-tested
  (`HARD_DECLINE`/`MANDATE_REVOKED`/`CUSTOMER_OPTED_OUT` as terminal preconditions;
  `MAX_ATTEMPTS`/`COST_CAP` as candidate-generation preconditions;
  `NEGATIVE_EXPECTED_VALUE` as the argmax fallback; `INSUFFICIENT_CONFIDENCE` via
  abstention).
- `agent/compliance.py`: all 15 rules from `docs/01-REGULATORY.md`'s table as declarative
  `Rule` objects. The gate runs **inside** candidate generation
  (`agent/decide.py::_generate_candidates` + `is_hard_compliant` filter before scoring),
  not as a post-hoc check. Several predicates are honestly trivial (`True` by
  construction — e.g. `CONDUCT-NO-SHAME` has no free-text/third-party-contact path to
  guard against in this closed action set) and documented as such rather than faked.
- `agent/decide.py`: the pure `decide(ctx, models, config) -> Decision` function. No I/O,
  no clock (`ctx.now` supplied), no LLM. Candidates: `ScheduleDebit` per (day, channel)
  in the legal window, `OfferDateChange` when a preferred day is declared, plus a
  `Stop`/`EscalateToHuman` baseline pair always scored at `E[net]=0.0`. Scoring uses
  `models/recovery.py` (P(success)), `models/hazard.py` (P(revoke) — **a reminder inline
  in the docstring that `hazard_per_failure_notification` is a declared assumption, not
  ground truth**, per the framing correction earlier this session), and `models/ltv.py`
  (LTV_remaining). The per-decision uncertainty band is called `confidence_band`, never
  `confidence_interval`/"CI" (that name is reserved for Phase 4's evaluation output) —
  a Wilson score interval on each probability using each model's training-time slice `n`
  as the effective sample size, chosen over the normal approximation because the latter
  undercovers at small `n` / near p=0,1, exactly the ABSTAIN-relevant regime. Documented
  as an approximation, not a real posterior. See `docs/DECISIONS.md` [2026-08-25] (two
  entries: the rename, and the Wilson switch).
- Abstention: all four triggers from the spec (thin `(bank,method)` slice, bank-health
  change-point, slice Brier over threshold, `E[net]` confidence band straddling zero),
  each with its own unit test.
- New model-loading plumbing that didn't exist before (Phase 2 only trained/persisted):
  `TrainedRecoveryModel`/`TrainedHazardModel` gained `load_*` classmethods and
  `predict_*_contrib` (LightGBM's native `pred_contrib`, the per-prediction feature
  attribution `PROGRESS.md` deferred from Phase 2). `agent/models.py::ModelBundle` /
  `load_model_bundle` is the single I/O boundary that assembles both models, the LTV life
  table, bank-health snapshots and each model's slice metrics for `decide()` to score
  against.
- `agent/audit.py`: append-only `AuditTrail` (`append()` only ever grows the record list)
  + `render()` producing the `SAW`/`THOUGHT`/`ALT`/`GATE`/`DID`/`WHY` block from
  `docs/06-AGENT-SPEC.md`'s example, generated entirely from structured fields (no LLM).
- `config/policy.yaml` + `agent/policy.py`: every tunable (`max_attempts_per_cycle`,
  `max_notifications_per_cycle`, `cost_cap_inr`, `human_signoff_threshold_inr`,
  `min_slice_n`, `max_slice_brier`, `holdout_fraction`, `retry_requires_fresh_pdn`,
  `converge_min_cycles_between_date_changes`), same `source:`/`assumption:` discipline as
  `sim/params.yaml`, loaded via the same `sim.params.load_params` validator.
- `hypothesis` property test (`tests/test_agent_decide.py`, 200 examples over randomized
  `DecisionContext`s): `decide()` never returns an action violating a HARD compliance
  rule. Separately, `tests/test_agent_compliance.py` proves the gate itself catches
  hand-built violating candidates (each HARD rule tested directly), since the property
  test alone only proves `decide()`'s own careful construction stays compliant.
  `tests/test_no_llm_in_money_path.py` broadened from `agent/decide.py` alone to the
  whole `agent/` package. 72 tests total, `make check` green.
- **Descoped from Phase 3, by design, not oversight:** `SendPreDebitNotice` is never
  generated as a free-standing top-level candidate (always embedded in `ScheduleDebit`);
  `OfferDateChange`'s `E[net]` is a flat placeholder (0.01) rather than modelled, since
  its real value needs the eval harness's response-rate mechanic (Phase 4); the human
  sign-off proposal *queue* (persistence/UI) is Phase 5, only the `requires_signoff` flag
  exists now. See `docs/DECISIONS.md` [2026-08-25] for the full reasoning on each.

**Done:**
- Track, loss class, thesis and objective function decided and written up
- Regulatory clearance research complete — no blockers found (`docs/01-REGULATORY.md`)
- Full architecture, data model, ML, agent, eval, frontend and demo specs written
- Technology choices made with reasoning and rejected alternatives (`docs/03-TECH-STACK.md`)
- Day-by-day plan and scope-cut order fixed (`PLAN.md`)
- Repo scaffolded: `pyproject.toml` (uv-managed), `Makefile`, module dirs, GitHub Actions CI
  (ruff + mypy strict on `agent/models/sim/features` + pytest + reduced-seed sim smoke run)
- Public GitHub repo created and pushed: `github.com/jaygautam-creator/Dobara`, branch `main`
- Razorpay test keys moved to gitignored `.env.local`; `.env.example` restored to placeholders
  (the repo's working copy had real test keys filled into `.env.example` at session start —
  fixed before anything was pushed; see the session note below)
- NPCI AutoPay figures pinned: 50M new registrations / 808M executions, July 2025, with the
  rejected "120M/month" figure and reasoning documented in `docs/04-DATA-MODEL.md` and README
- Full simulator built (`sim/`): SQLAlchemy schema, sourced `sim/params.yaml` + validator,
  isolated latent balance/bank generators, TD/BD bank priors + 3 real dated 2025 outages +
  day-of-week profile, `rejected_no_pdn` mechanic, notification→revocation hazard coupling,
  date-change offer (incl. `response_rate: 0.0` capability), temporal/cold-start/regime-shift
  splits, reproducible-from-seed. 17 tests passing; `make sim` at n=5000 runs in ~10s and
  lands inside the declared benchmark sanity bands (failure 20.2%, recovery 46.4%,
  revocation 9.1%/mandate/8-cycles)

- Calibration made real, not just printed: `tests/test_calibration.py` runs 5 seeds and
  asserts the MEAN of each metric against its band, CI-enforced. Added the harder
  `revocation_per_execution_ratio ≈ 2.5%` benchmark (20M revocations ÷ 808M executions/month,
  both already pinned) and recalibrated the revocation hazard to hit it — was
  under-producing ~2.2x. That pulled `recovery_rate`'s mean to ~41%, so its band tightened
  to (0.28, 0.48), close to the published 30-45% average.
- Fixed a real Phase 1 gap found while building Phase 2: `Customer` rows (`bank_id`,
  `segment`, `preferred_debit_day`) were never persisted to the schema — only the hidden
  `CustomerLatent` held `bank_id`. `bank_id` is observable (a PSP knows it from the VPA),
  not latent, so this blocked any join from a mandate to its customer's bank. Fixed in
  `sim/engine.py`; `preferred_debit_day` is now set when a date-change offer is accepted
  (Tier 1 evidence).
- Bank health (Model 3): `models/bank_health.py` — EWMA with adaptive decay (decay rises
  with recent outcome variance) + a rolling change-point flag, per (bank × method). Writes
  a `BankHealthSnapshot` after every attempt.
- Feature builder (Phase 2 foundation): `features/recovery.py` — `build_recovery_features()`
  emits one row per historical `Attempt` with all 25 feature columns from `docs/05-ML-SPEC.md`
  Model 1, computed strictly from data before that attempt's `scheduled_at` (prior
  attempts/cycles on the same mandate; an as-of join against bank-health snapshots strictly
  before the timestamp, never the snapshot the attempt itself produced).
  `assert_no_banned_features()` blocks any column name containing balance/income/spend/etc.
  Leakage test (`tests/test_features_leakage.py`) mutates a later attempt's outcome and
  asserts every earlier row's features are unchanged. 30 tests total, all green.

- Hardened the leakage test per user review: `_compare_cols()` now asserts the full
  declared feature list + label is present before comparing (a renamed column could
  otherwise silently narrow the check and still pass — same failure mode as a print-only
  benchmark). Added a second leakage case that INSERTs a new later attempt (rather than
  mutating an existing one) to catch a feature reading the mere *existence* of a future
  row — a bug class the mutation-only test can't see. Caught a real bug while writing it:
  a raw-SQL datetime literal read back in a different textual format than SQLAlchemy
  ORM-written rows, and pandas silently turned the mismatched rows into `NaT`.
- README reframed the banned-feature guard honestly: a stated commitment backed by import
  isolation + review, not a proof — it's name-based and catches naming, not semantics.
- Fixed `Revocation.trigger_attempt_id` (was always `None` — needed to label exactly which
  attempt triggered a revocation for the hazard model).
- Fixed the `make sim` → `make train` wiring gap: `sim/run.py` was writing
  `data/dobara_seed0.sqlite3` by default while `models/train.py` read
  `data/dobara.sqlite3` — the two had never been run back-to-back before. A single default
  run (no `--seed`/`--seeds`/`--out`) now writes the canonical `data/dobara.sqlite3`;
  multi-seed sweeps keep the per-seed naming.
- **Recovery model** (`models/recovery.py`): LightGBM + logistic baseline, isotonic
  calibration, Brier-led metric blocks with bootstrap CIs (`models/metrics.py`, shared with
  the hazard model), slice metrics by bank/method/attempt-index/regime-shift-bank. Real
  test-set result: LightGBM and logistic are essentially tied (Brier 0.1219 vs 0.1220) —
  reported honestly via `beats_baseline`, not oversold. Regime-shift-bank slice is visibly
  worse-calibrated (Brier 0.179 vs 0.113), which is the ABSTAIN signal Phase 3 needs.
- **Revocation hazard model** (`features/hazard.py` + `models/hazard.py`): discrete-time
  hazard, exposure unit is one row per `soft_decline` attempt (not per calendar day —
  documented why in the module docstring: `sim/engine.py` only evaluates hazard there).
  Headline number: hazard rises 0.113 → 0.130 → 0.207 as same-cycle failure count goes
  0 → 1 → 2. **This does not confirm the thesis empirically** —
  `hazard_per_failure_notification` is a declared assumption in `sim/params.yaml`
  (recalibrated 2026-08-25), so the rising-hazard relationship was put into the generator
  by hand and the model is recovering it. What this result actually shows is that the
  hazard model is correctly specified: it recovers a known relationship from data, which
  validates the model, not the world. See the correction in `docs/DECISIONS.md`
  [2026-08-25] and the README's "Circularity and what our numbers can and cannot show"
  section. Survival-curve conversion included.
- **LTV estimator** (`models/ltv.py`): transparent Kaplan-Meier-style life table by
  `(merchant_category, mandate_age_cycles)` from real simulated data, not model
  predictions. `margin_factor` assumption (0.7, range [0.4, 0.9]) added to
  `sim/params.yaml`'s new `ltv:` block for the Phase 4 sensitivity analysis.
- `models/train.py` CLI wires all three together; `make sim && python -m models.train`
  runs end-to-end. 40 tests total, all green via `make check`.

**In progress:** nothing.

**Next action:** Day 6 — Phase 4 (evaluation, **the gate**), spec
`docs/07-EVAL-SPEC.md`. Build the batch harness over all five arms (`do_nothing`,
`razorpay_default`, `aggressive_8x`, `dobara`, `oracle`), 30 seeds with paired comparisons
and bootstrap CIs, all nine metrics incl. net LTV/revocations caused/attempts not made,
the money chart (gross vs net LTV crossover), and — this is now the load-bearing item
given this session's circularity correction (`docs/DECISIONS.md` [2026-08-25]) — the
**sensitivity analysis across the full declared `sensitivity_range` [0.05, 0.15]** of
`revocation.hazard_per_failure_notification`, plus the **break-even statement**: the
hazard value below which `aggressive_8x` would win. That comparison, not the Phase 2
hazard headline, is what actually has to carry the thesis.

**Blockers:** none.

**Session note for the user:** at the start of this session `.env.example` had real
Razorpay test key ID/secret filled in (not placeholders) and was about to be pushed to the
new public GitHub repo. Fixed: real keys moved to `.env.local` (gitignored), `.env.example`
restored to `rzp_test_xxxxxxxxxxxx` placeholders, confirmed with you before touching git.
Worth remembering for future sessions: don't fill real credentials into `.env.example`.

**Open items for the user:** none outstanding — Razorpay test keys are in `.env.local`,
GitHub repo is created and pushed.

---

## Phase 0 — Foundation ✅

- [x] Track chosen (03), loss class narrowed
- [x] Thesis + motto locked
- [x] Regulatory research — no blockers
- [x] Architecture designed
- [x] Tech stack chosen with justification
- [x] Plan + scope-cut order
- [x] Session-handoff system (`CLAUDE.md`, this file, `SESSION-PROMPT.md`)
- [x] Repo scaffolded (`pyproject.toml`, `Makefile`, dirs, CI, `.env.example`)
- [x] Public GitHub repo created and pushed (`github.com/jaygautam-creator/Dobara`, branch `main`)
- [x] Razorpay test keys in `.env.local` (gitignored; `.env.example` kept as placeholders)

## Phase 1 — Simulator (Day 1–2) · spec: `docs/04-DATA-MODEL.md`

- [x] **Pin real NPCI AutoPay figures**; document the press discrepancy in README
- [x] SQLAlchemy schema for all entities; SQLite target (`sim/schema.py`)
- [x] `sim/params.yaml` — every parameter has `source:` or `assumption: true`
- [x] Param validator: unsourced + unflagged parameter fails `make check` (`sim/params.py`, tested)
- [x] Latent state (customer balance process, bank profiles) — **isolated from `features/`** (`sim/latent.py` + import-boundary test)
- [x] Bank behaviour: TD/BD priors, day-of-week profile, correlated outage injection (3 real dated 2025 UPI outages + background minor-outage rate)
- [x] `rejected_no_pdn` outcome modelled (retry without valid PDN is rejected, not declined) — unit-tested
- [x] Notification → revocation hazard coupling (`revocation_hazard()`)
- [x] Date-change offer response modelled, incl. a `response_rate: 0.0` configuration (default 6%, sensitivity range down to 0.0)
- [x] `make sim` reproducible from seed (hash-identical output across runs, tested; diverges across seeds, tested)
- [x] **Validation: output matches published benchmarks, CI-enforced** — `tests/test_calibration.py` runs 5 seeds and asserts the MEAN of each metric against its band (fails the build on regression); `sim/run.py`'s BENCHMARKS stays print-only for `make sim` readability. Includes the harder benchmark `revocation_per_execution_ratio ≈ 2.5%` (20M revocations ÷ 808M executions/month, both pinned in `docs/04-DATA-MODEL.md`) — the revocation hazard was recalibrated to hit it (was under-producing ~2.2x, the conservative direction). `recovery_rate` band tightened to (0.28, 0.48), close to the published 30-45% average, once that recalibration pulled the simulated mean to ~41%. See `docs/DECISIONS.md` [2026-08-25].
- [x] Splits: temporal (1–4 / 5 / 6–8), cold-start mandates, regime-shift bank in test only (`sim/splits.py`; regime-shift bank = SBI, injected from cycle 6)
- [x] Leakage test: no feature reads post-decision data (`tests/test_features_leakage.py` — mutate a later attempt's outcome, recompute, assert every earlier row's features are byte-identical)
- [x] Isolation test: `features/` cannot import latent tables (`tests/test_latent_isolation.py`, AST-based, passes on real `features/recovery.py` code now)

## Phase 2 — Models (Day 3–4) · spec: `docs/05-ML-SPEC.md`

- [x] Feature builder with strict as-of boundary (`features/recovery.py`: `build_recovery_features()`, one row per historical `Attempt`, all 25 spec-named columns, as-of join against bank-health snapshots)
- [x] Banned-feature test (nothing encoding individual balance/income) — `tests/test_features_banned.py`, `assert_no_banned_features()` checked both statically on the declared column list and on the built DataFrame
- [x] Recovery model: LightGBM + **logistic baseline reported alongside** (`models/recovery.py`; test-set result: LightGBM Brier 0.1219 vs logistic 0.1220 — essentially tied, reported honestly as `beats_baseline` rather than oversold)
- [x] Isotonic calibration on validation split (cycle 5, both models)
- [x] Brier score + reliability diagram — **led before AUC** (`models/metrics.py::metric_block`, Brier is the first key; AUC 0.735 lightgbm / 0.733 logistic)
- [x] Slice metrics: bank, method, attempt index, cold-start, regime-shift bank separately (`_slice_metrics` in `models/recovery.py`; regime-shift bank slice Brier 0.179 vs 0.113 non-regime — visibly worse-calibrated, exactly the ABSTAIN signal the design depends on)
- [x] Revocation hazard: person-period frame, LightGBM, survival conversion (`features/hazard.py` + `models/hazard.py`; exposure unit is per-`soft_decline`-attempt, not per-calendar-day — see the module docstring for why a daily grid would be wrong for this simulator's actual hazard mechanism)
- [x] Hazard calibration + reliability diagram (isotonic on validation, same `metric_block` treatment)
- [x] Headline interpretable output: marginal hazard per additional failure notification (`marginal_hazard_by_failure_count()`; real run: 0→1 failures +1.7pp, 1→2 failures +7.7pp — the hazard model correctly recovers the rising-hazard relationship the simulator was given as a declared assumption; this validates the model's specification, not the thesis — see `docs/DECISIONS.md` [2026-08-25])
- [x] Bank health: EWMA with adaptive decay + change-point flag (`models/bank_health.py`; writes a `BankHealthSnapshot` per attempt, consumed as-of by `features/recovery.py`)
- [x] LTV estimator (transparent, assumption range declared) — `models/ltv.py`: Kaplan-Meier-style life table by `(merchant_category, mandate_age_cycles)` built directly from simulated Mandate/Cycle/Revocation data (not the hazard model's predictions); `margin_factor` assumption (0.7, range [0.4, 0.9]) added to `sim/params.yaml`'s new `ltv:` block for the Phase 4 sensitivity analysis
- [x] Model versioning hash recorded (`model_version` in both `recovery_model_report.json` and `hazard_model_report.json`; not yet wired into an audit line since `agent/audit.py` doesn't exist until Phase 3)
- [ ] Per-prediction feature attribution retained — deferred to Phase 3 (`agent/decide.py` is where predictions become audited decisions)

## Phase 3 — Agent (Day 5) · spec: `docs/06-AGENT-SPEC.md`

- [x] `Action` closed enum; nothing outside it representable (`agent/actions.py`)
- [x] `decide()` as a pure function — no I/O, no clock, no LLM (`agent/decide.py`)
- [x] Candidate generation over legal times/channels, floored at now+24h
- [x] Declarative compliance rules with `id`/`citation`/`severity`/`source_url` (`agent/compliance.py`, all 15 rules from `docs/01-REGULATORY.md`)
- [x] Gate runs **inside** candidate generation (structural, not advisory)
- [x] **`hypothesis` property test: no generated action ever violates a HARD rule** (`tests/test_agent_decide.py::test_decide_never_returns_an_action_violating_a_hard_rule`, 200 examples)
- [x] Seven named stopping reasons (`agent/stopping.py`; all seven reachable and unit-tested)
- [x] Abstention paths (slice size, change-point, calibration error, CI straddling zero) — all four unit-tested
- [x] `Decision` carries rejected alternatives with their own E[net]
- [x] Audit trail: append-only, structured + human-readable rendering (`agent/audit.py`)
- [x] Human sign-off **threshold** (`Decision.requires_signoff`) — the proposal-queue UI/persistence itself is out of scope for Phase 3, deferred to Phase 5 (`api/`/`web/`)
- [x] Import-boundary test: no LLM import anywhere in `agent/` (`tests/test_no_llm_in_money_path.py`, broadened from `decide.py` alone to the whole package)

## Phase 4 — Evaluation (Day 6) · **THE GATE** · spec: `docs/07-EVAL-SPEC.md`

**Status note (2026-08-25):** every item below has code that implements it and the
harness runs end-to-end, but boxes stay unticked until a *post-oracle-fix* full 30-seed
run completes and the `dobara`-vs-`do_nothing` finding is resolved one way or the other —
see the `## CURRENT STATE` note above. Ticking these now would overclaim a validated
result the project doesn't have yet.

- [ ] Arm: `do_nothing`
- [ ] Arm: `razorpay_default` (their documented behaviour, cited)
- [ ] Arm: `aggressive_8x`
- [ ] Arm: `dobara`
- [ ] Arm: `oracle`
- [ ] 30 seeds; seed variance + bootstrap CIs
- [ ] **Paired comparisons on identical seeds**; non-significance stated plainly
- [ ] All nine metrics per arm incl. net LTV, revocations caused, attempts not made
- [ ] The money chart: gross vs net LTV, crossover annotated
- [ ] Sensitivity analysis across every declared range, incl. response_rate 0%
- [ ] **Break-even statement**: hazard value at which `aggressive_8x` would win
- [ ] Robustness slices reported separately
- [ ] Permanent holdout arm implemented as a product feature
- [ ] `artifacts/summary.json` + `artifacts/results.parquet` written
- [ ] Test-set evaluation count recorded as an honesty marker
- [ ] **GATE CHECK: numbers exist. If not — cut frontend, see `PLAN.md`.**

## Phase 5 — API + Razorpay (Day 7) · spec: `docs/02-ARCHITECTURE.md`

- [ ] FastAPI app, Pydantic contracts, OpenAPI schema
- [ ] SSE streaming batch endpoint (+ polling fallback)
- [ ] Audit record endpoints
- [ ] Razorpay test-mode client: create subscriptions, trigger charges, receive webhooks
- [ ] `success@razorpay` / `failure@razorpay` outcome forcing wired into the demo
- [ ] Actions emitted as **proposals**, never direct rail calls

## Phase 6 — Frontend (Day 8) · spec: `docs/08-FRONTEND-SPEC.md`

- [ ] **Load the `dataviz` skill before writing chart code**
- [ ] Next.js scaffold, Tailwind, shadcn/ui, generated API types
- [ ] `/` thesis page with inline sources
- [ ] `/control-room` — counters incl. "attempts not made", queue, decision cards, gate animation
- [ ] **The comparison toggle** (aggressive vs Dobara)
- [ ] `/evidence` — five arms with CIs, money chart, calibration first, sensitivity, break-even, honesty panel
- [ ] `/audit/[id]`
- [ ] `/mandate/[id]` timeline
- [ ] Abstention banner
- [ ] Deployed demo works with **no API key**

## Phase 7 — Ship (Day 9–10)

- [ ] Architecture diagram (mermaid + SVG)
- [ ] README: problem, thesis, approach, metrics **read from `summary.json`**, run instructions
- [ ] README: assumptions table, unsourced parameters, regulatory grey area, break-even
- [ ] README: **"What Dobara deliberately does not do"**
- [ ] README: RBI FREE-AI Sutra mapping table
- [ ] README: "not legal advice" disclaimer; "Razorpay test mode, no affiliation" note
- [ ] CI green: ruff, mypy strict, pytest, reduced-seed eval
- [ ] Consistency check: every README number matches `summary.json`
- [ ] Deploy to Vercel `bom1`
- [ ] Record 5-min video per `docs/09-DEMO-SCRIPT.md`
- [ ] Submit

---

## Session log

Append one line per session: date · what was done · what is next.

- **2026-08-24** — Day 0. Research, thesis, regulatory clearance, full specification, plan, handoff system. Next: Day 1 scaffold + simulator.
- **2026-08-25** — Day 1. Fixed real Razorpay test keys accidentally left in `.env.example` (moved to gitignored `.env.local`). Scaffolded repo (`pyproject.toml`, `Makefile`, CI) and pushed to `github.com/jaygautam-creator/Dobara`. Pinned NPCI AutoPay figures (50M/808M, July 2025) with sourcing reasoning. Built the full simulator (`sim/`): schema, sourced params + validator, isolated latent state, bank/outage/dow calibration, `rejected_no_pdn`, revocation hazard, date-change offer, splits, reproducibility. 17 tests green; `make sim` validated against benchmark sanity bands.
- **2026-08-25** — Day 1, gap-closing pass before Phase 2. Made the calibration check real: `tests/test_calibration.py` runs 5 seeds and fails CI on a regressed mean; the print-only version stays in `make sim`. Added the harder `revocation_per_execution_ratio ≈ 2.5%` benchmark (derived from the two already-pinned 20M/808M figures) and recalibrated the revocation hazard to hit it — was under-producing revocations ~2.2x, the conservative direction, corrected anyway. That recalibration pulled `recovery_rate` to ~41%, so tightened its band from (0.15, 0.75) to (0.28, 0.48). 21 tests green. Next: Phase 2 — `features/` + recovery/hazard models per `docs/05-ML-SPEC.md`.
- **2026-08-25** — Day 1-3, Phase 2 start. Fixed a Phase 1 gap: `Customer` rows (`bank_id` — observable, not latent) were never persisted, discovered while building the feature builder. Built `models/bank_health.py` (EWMA + adaptive decay + change-point flag) and `features/recovery.py` (strict as-of feature builder, 25 columns per `docs/05-ML-SPEC.md`, banned-feature guard, leakage test). 30 tests green. Next: recovery model, revocation hazard model, LTV estimator.
- **2026-08-25** — Day 4, Phase 2 complete. Hardened the leakage test (completeness guard on compared columns; a second case that inserts rather than mutates, catching a different bug class — caught a real raw-SQL-datetime/pandas-parsing bug while writing it). Reframed the banned-feature guard honestly in the README (commitment + review, not proof). Fixed `Revocation.trigger_attempt_id` (was always `None`) and the `sim.run`→`models.train` default-db-path wiring gap. Built the recovery model, the revocation hazard model (with a documented per-soft-decline-attempt exposure unit and a headline marginal-hazard number: 0.113→0.130→0.207 as same-cycle failures go 0→1→2), and the LTV life-table estimator. `models/train.py` CLI wires all three; `make sim && python -m models.train` runs end-to-end. 40 tests green. Next: Phase 3 — agent (`docs/06-AGENT-SPEC.md`).
- **2026-08-25** — Day 4-5, framing correction before Phase 3. The 0.113→0.130→0.207 hazard result was mis-described above as empirically confirming the thesis. It does not: `hazard_per_failure_notification` is a declared assumption in `sim/params.yaml` (recalibrated 2026-08-25), so the rising-hazard relationship was authored into the generator by hand, and the hazard model recovering it is circular — exactly the failure mode the hidden-latent-state design exists to prevent. Corrected everywhere it appeared (`PROGRESS.md`, `models/hazard.py` docstring) and added a "Circularity and what our numbers can and cannot show" section to the README distinguishing what the result actually shows (correct model specification) from what supports the thesis (the regulatory mechanism + the 20M/808M published figures, not fitted parameters). Full entry in `docs/DECISIONS.md` [2026-08-25]. Phase 4 will need to show the defensible claim instead: Dobara beats `aggressive_8x` on net LTV across the full declared `sensitivity_range` [0.05, 0.15] of `hazard_per_failure_notification`, plus the break-even value. Next: Phase 3 — agent (`docs/06-AGENT-SPEC.md`).
- **2026-08-25** — Day 5, Phase 3 complete. Built the whole decision layer from scratch: closed `Action` type (`agent/actions.py`), seven stopping reasons (`agent/stopping.py`), all 15 compliance rules from `docs/01-REGULATORY.md` as a declarative, structurally-enforced gate (`agent/compliance.py`), the pure `decide()` function with candidate generation/scoring/abstention (`agent/decide.py`), an append-only audit trail with the spec's `SAW`/`THOUGHT`/`ALT`/`GATE`/`DID`/`WHY` rendering (`agent/audit.py`), a sourced `config/policy.yaml` + loader (`agent/policy.py`), and the model-loading plumbing Phase 2 never built (`load_recovery_model`/`load_hazard_model`, `predict_*_contrib` for per-decision feature attribution, `agent/models.py::ModelBundle`). Added a `hypothesis` property test (200 examples: `decide()` never violates a HARD rule) plus direct gate tests proving each HARD rule actually blocks a hand-built violating candidate (the property test alone only proves `decide()`'s own output stays compliant, not that the gate would catch a bug). 72 tests total, `make check` green. Two things worth flagging: the per-decision confidence interval is an explicitly-approximate normal approximation to the binomial proportion CI using each model's training-time slice `n` (no real predictive posterior exists yet — documented as an approximation in `agent/decide.py`'s docstring, not oversold); and `OfferDateChange` is scored at a flat placeholder value pending Phase 4's response-rate mechanic. Full reasoning for both, plus the ESCALATE_TO_HUMAN-scoring and ABSTAIN/STOP(INSUFFICIENT_CONFIDENCE) design calls, in `docs/DECISIONS.md` [2026-08-25]. Next: Phase 4 — evaluation, the gate (`docs/07-EVAL-SPEC.md`).
- **2026-08-25** — Day 5, two refinements to the per-decision uncertainty band before Phase 4 widened its call sites. (1) Renamed `Decision.confidence_interval` -> `confidence_band` everywhere (`agent/context.py`, `agent/decide.py`, `agent/audit.py`, `docs/06-AGENT-SPEC.md`, `docs/04-DATA-MODEL.md`, `sim/schema.py`'s unused `confidence_band_json` column) — "CI" is now reserved exclusively for Phase 4's evaluation-harness bootstrap/seed-variance intervals, so an acknowledged per-decision approximation can never be mistaken for a sound evaluation estimate on an audit card or `/evidence`. (2) Replaced the normal approximation to the binomial proportion CI with the Wilson score interval (`agent/decide.py::_wilson_interval`, was `_proportion_ci`) — the normal approximation undercovers at small `n` and near p=0/1, exactly the thin-slice/low-hazard regime the band adjudicates for `ABSTAIN`. Both documented in `docs/DECISIONS.md` [2026-08-25]. `make check` green, no test call sites broken (none existed yet). Next: Phase 4 — evaluation, the gate (`docs/07-EVAL-SPEC.md`); note it now carries more argumentative weight than originally planned, since the sensitivity analysis across `hazard_per_failure_notification`'s full declared range plus the break-even statement ARE the empirical case for the thesis, not supporting material (see the framing-correction entry above).
- **2026-08-25** — Day 6, Phase 4 harness built end-to-end (`eval/world.py`/`rng.py`/`arms.py`/`runner.py`/`metrics.py`/`sensitivity.py`/`run.py`), `agent/decide.py` batch-score-optimized (~26x, characterization-tested), and a real full 30-seed x 5-arm run completed (~110 min). Before accepting it, verification found the `oracle` arm violated its own dominance property (underperformed `do_nothing` and `dobara` on net LTV — should be impossible for the arm with the most information) because it only used foresight for day-selection, never for deciding whether to retry at all. **Fixed**: oracle now stops each cycle the instant the true (closed-form, not estimated) expected net value of another attempt is non-positive; verified at smoke scale it now dominates every arm. Separately, that completed run also showed `dobara` underperforming `do_nothing` (more attempts, more notifications, fewer successes, more revocations, lower net LTV) — investigated three hypotheses (documented in `docs/DECISIONS.md`), found `agent/decide.py`'s `E[net]` formula uses the hazard model's output unweighted by `P(failure)`, which structurally overstates the revocation downside — but this exact form is also what `docs/06-AGENT-SPEC.md`'s own worked example uses, so it may be a spec-level choice, not a Phase 3 implementation bug, and fixing it would both touch already-shipped/reviewed/characterization-tested code AND happen to point toward making `dobara` look better — deliberately **not fixed** without the user's sign-off. `artifacts/results.parquet`/`summary.json` on disk right now predate the oracle fix and must not be treated as final. `make check` green (73 tests). Next: user decides how to resolve the `dobara`-vs-`do_nothing` question, then rerun the full 30-seed harness (~2h) with the oracle fix in place.
