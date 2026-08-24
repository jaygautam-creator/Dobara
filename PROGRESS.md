# PROGRESS — Dobara

> **This file is the source of truth for session handoff.**
> Every session: read `## CURRENT STATE` first. Every session: rewrite it before finishing.

---

## CURRENT STATE

**Last updated:** 2026-08-25 (Day 1 session)
**Phase:** Phase 0 + Phase 1 (simulator) complete. Ready to begin Phase 2 (models).

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

**In progress:** nothing.

**Next action:** Day 3 — Phase 2 (models), spec `docs/05-ML-SPEC.md`. Build `features/`
(strict as-of boundary, banned-feature test for individual balance/income), then the
recovery model (LightGBM + logistic baseline, isotonic calibration, Brier score before AUC),
then the revocation hazard model (person-period, LightGBM, survival conversion), then bank
health EWMA + change-point flag.

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
- [ ] Leakage test: no feature reads post-decision data — deferred to Phase 2, `features/` doesn't exist as real code yet
- [x] Isolation test: `features/` cannot import latent tables (`tests/test_latent_isolation.py`, AST-based, passes on the current empty `features/`)

## Phase 2 — Models (Day 3–4) · spec: `docs/05-ML-SPEC.md`

- [ ] Feature builder with strict as-of boundary
- [ ] Banned-feature test (nothing encoding individual balance/income)
- [ ] Recovery model: LightGBM + **logistic baseline reported alongside**
- [ ] Isotonic calibration on validation split
- [ ] Brier score + reliability diagram — **led before AUC**
- [ ] Slice metrics: bank, method, attempt index, cold-start, regime-shift bank separately
- [ ] Revocation hazard: person-period frame, LightGBM, survival conversion
- [ ] Hazard calibration + reliability diagram
- [ ] Headline interpretable output: marginal hazard per additional failure notification
- [ ] Bank health: EWMA with adaptive decay + change-point flag
- [ ] LTV estimator (transparent, assumption range declared)
- [ ] Model versioning hash recorded in audit lines
- [ ] Per-prediction feature attribution retained

## Phase 3 — Agent (Day 5) · spec: `docs/06-AGENT-SPEC.md`

- [ ] `Action` closed enum; nothing outside it representable
- [ ] `decide()` as a pure function — no I/O, no clock, no LLM
- [ ] Candidate generation over legal times/channels, floored at now+24h
- [ ] Declarative compliance rules with `id`/`citation`/`severity`/`source_url`
- [ ] Gate runs **inside** candidate generation (structural, not advisory)
- [ ] **`hypothesis` property test: no generated action ever violates a HARD rule**
- [ ] Seven named stopping reasons
- [ ] Abstention paths (slice size, change-point, calibration error, CI straddling zero)
- [ ] `Decision` carries rejected alternatives with their own E[net]
- [ ] Audit trail: append-only, structured + human-readable rendering
- [ ] Human sign-off threshold and proposal queue
- [ ] Import-boundary test: `agent/decide.py` has no LLM import

## Phase 4 — Evaluation (Day 6) · **THE GATE** · spec: `docs/07-EVAL-SPEC.md`

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
