# PROGRESS — Dobara

> **This file is the source of truth for session handoff.**
> Every session: read `## CURRENT STATE` first. Every session: rewrite it before finishing.

---

## CURRENT STATE

**Last updated:** 2026-08-24 (Day 0, Opus planning session)
**Phase:** Day 0 complete — specification locked. Ready to begin Day 1.

**Done:**
- Track, loss class, thesis and objective function decided and written up
- Regulatory clearance research complete — no blockers found (`docs/01-REGULATORY.md`)
- Full architecture, data model, ML, agent, eval, frontend and demo specs written
- Technology choices made with reasoning and rejected alternatives (`docs/03-TECH-STACK.md`)
- Day-by-day plan and scope-cut order fixed (`PLAN.md`)

**In progress:** nothing.

**Next action:** Day 1 — Phase 1 below. Scaffold the repo, then build the simulator.
Start by pinning the real NPCI AutoPay figures (see the BUILD TASK in `docs/04-DATA-MODEL.md`).

**Blockers:** none.

**Open items for the user:**
- [ ] Create Razorpay test-mode account, generate Test API keys, put them in `.env.local`
- [ ] Create the public GitHub repo and add the remote

---

## Phase 0 — Foundation ✅

- [x] Track chosen (03), loss class narrowed
- [x] Thesis + motto locked
- [x] Regulatory research — no blockers
- [x] Architecture designed
- [x] Tech stack chosen with justification
- [x] Plan + scope-cut order
- [x] Session-handoff system (`CLAUDE.md`, this file, `SESSION-PROMPT.md`)
- [ ] Repo scaffolded (`pyproject.toml`, `Makefile`, dirs, CI, `.env.example`)
- [ ] Public GitHub repo created and pushed
- [ ] Razorpay test keys in `.env.local`

## Phase 1 — Simulator (Day 1–2) · spec: `docs/04-DATA-MODEL.md`

- [ ] **Pin real NPCI AutoPay figures**; document the press discrepancy in README
- [ ] SQLAlchemy schema for all entities; SQLite target
- [ ] `sim/params.yaml` — every parameter has `source:` or `assumption: true`
- [ ] Param validator: unsourced + unflagged parameter fails `make check`
- [ ] Latent state (customer balance process, bank profiles) — **isolated from `features/`**
- [ ] Bank behaviour: TD/BD priors, day-of-week profile, correlated outage injection
- [ ] `rejected_no_pdn` outcome modelled (retry without valid PDN is rejected, not declined)
- [ ] Notification → revocation hazard coupling
- [ ] Date-change offer response modelled, incl. a `response_rate: 0.0` configuration
- [ ] `make sim` reproducible from seed
- [ ] **Validation: output matches published benchmarks** (failure rate, recovery rate, revocation ratio)
- [ ] Splits: temporal (1–4 / 5 / 6–8), cold-start mandates, regime-shift bank in test only
- [ ] Leakage test: no feature reads post-decision data
- [ ] Isolation test: `features/` cannot import latent tables

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
