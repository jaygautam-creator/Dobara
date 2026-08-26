# 03 — Technology Choices (and what we rejected)

**Principle:** every choice must earn a point with the judges. The judged artifact is
*decision quality, measurement rigour, compliance modelling, and how the repo reads*.
Technology that does not serve those is a tax. Total cost must be **₹0**.

Second principle: **a judge must be able to `git clone` and run it in one command with no
API keys and no cloud account.** Reproducibility is the track's actual bar. Every choice
below is filtered through that.

---

## Language

### Backend + ML: **Python 3.12** — chosen

- The judged core is `LightGBM` + `scikit-learn` + `scipy` + `numpy` + `pandas`. No other
  ecosystem is close for calibrated tabular modelling and statistical evaluation.
- Models and the agent live in **one process**. No serialisation boundary, no cross-language
  RPC, no drift between a Python model and a non-Python caller.
- `pip install -r requirements.txt` is a reproducibility story any judge can execute.

### Frontend: **TypeScript** — chosen
Non-negotiable for a Next.js app; types generated from the backend's OpenAPI schema so the
API contract is enforced across the boundary.

### **Rust — considered and rejected. Here is the reasoning.**

You asked specifically. The honest answer is that Rust would make this project *worse*, and
knowing that is itself the engineering judgement being tested.

| Argument for Rust | Why it does not apply here |
|---|---|
| Performance | Our heaviest job is 30 seeds × ~5,000 mandates × ~8 cycles. Vectorised NumPy runs it in seconds. We have no performance constraint to optimise. |
| Memory safety | We are not writing systems software. A miscalibrated probability is our failure mode, not a use-after-free. |
| Impressiveness | Judges are payments engineers reading for decision quality and honest metrics. A Rust rewrite of `argmax` impresses nobody. |
| Correctness via types | Pydantic + mypy strict gives us typed contracts at a fraction of the cost. |

**Against:** no mature Rust equivalent of LightGBM + isotonic calibration + bootstrap CI
tooling; we would hand-roll gradient boosting or FFI back to Python anyway. On a 10-day
solo budget it would consume ~40% of the time on plumbing that earns zero points, and it
would make the repo *harder* for a judge to run.

**Where Rust would be the right answer, and we say so in the README:** if this graduated
into Razorpay's real-time path — a scoring service on the hot path of 808M monthly mandate
executions — the inference service is a genuine Rust or Go candidate. The offline
decisioning, evaluation and simulation stay Python. *Knowing when Rust is right, and
correctly concluding this is not that, is the signal.*

---

## Backend framework: **FastAPI** — chosen

- Same process as the models. Zero boundary.
- Pydantic models give typed request/response contracts, automatic OpenAPI, and generated
  TypeScript types for the frontend. A typed API contract reads as professional.
- Native async SSE streaming for the live Control Room batch run.

**Rejected:** Django (ORM/admin weight we do not need), Flask (no typing story, no async),
Node backend (would put a serialisation boundary between the agent and its models).

---

## Hosting: **Vercel, static only — REVISED 2026-08-26, before Phase 6.** The Python API
does not get deployed. It stays a documented local mode (`make api`).

**This reverses this section's original plan** (Vercel Fluid Compute running the Python
API live, Neon Postgres backing it — kept below, struck through in spirit, for the
record). The original reasoning — Cloudflare Workers' Pyodide runtime cannot load
`lightgbm`/`scipy` native wheels, so Cloudflare was never viable for the model stack —
still stands and is not what changed. What changed is the deploy target for that Python
process, decided the same session Phase 5 shipped, before any frontend fetch call was
written:

> Vercel's Python runtime plus `lightgbm`/`scikit-learn`/`pandas` sits at or near the
> unzipped function size limit. The free alternatives that *do* fit (Render, Fly) sleep
> when idle — a judge opening the submission link at 11pm and watching a 30-60s
> cold-start spinner before anything renders is a materially worse outcome than any
> amount of architectural purity gained by serving the live agent from the deployed site.

**So: the deployed frontend is a static Vercel site reading `artifacts/*.json` — the
same committed evidence files `git clone` gets — never calling a deployed Python
backend.** `/evidence`, `/control-room`'s demo data, and `/mandate` all read committed
JSON (`artifacts/summary.json`, `sensitivity.json`, and the `make demo-fixture` output
`artifacts/demo_batch.json` — see `docs/DECISIONS.md` [2026-08-26], "data-shipping
architecture"). The **live** Python API (`make api`, real `agent.decide()` calls,
Razorpay test-mode proposal endpoints) is a **local-only, documented mode** — the README
says so — not something a judge's browser ever talks to. Postgres/Neon accordingly drops
out entirely: there is no deployed Python process that would need a database, ephemeral
filesystem or not.

Everything else about the frontend hosting choice is unaffected: Vercel remains chosen
for Next.js hosting, `bom1` (Mumbai) region, ₹0 Hobby tier, Hobby-is-non-commercial
caveat stated honestly for a hackathon submission.

- **Cloudflare is not dismissed** for a pure-static mirror or an edge cron — it simply
  never could have hosted the Python model stack, which is now moot for the deploy
  target anyway since that stack isn't deployed at all.

---

## Database: **SQLite only. No deployed database.**

One SQLAlchemy schema, SQLite always — the Postgres/Neon plan below is superseded by the
2026-08-26 hosting revision above (no deployed Python process, so nothing needs a
deployed database).

- **SQLite is the primary choice, and it is a deliberate one.** A judge runs
  `git clone && make demo` and everything works with zero infrastructure. The database
  file is a build artifact, reproducible from `make sim`. For a submission judged by
  reading and running a repo, that is worth more than any hosted feature.
- **Superseded: Neon (free tier, via Vercel Marketplace) for a deployed demo API.** The
  original plan assumed the Python API itself would be deployed to Vercel; the
  2026-08-26 hosting revision above rules that out entirely (unzipped function size,
  cold-start risk on the sleep-prone free alternatives), so there is no deployed backend
  process left that would need Neon or any other hosted database. The **scope-cut
  fallback this section originally described as a fallback — the deployed demo serving
  precomputed run artifacts committed to the repo — is now simply the design**, not a
  contingency: see `docs/DECISIONS.md` [2026-08-26] and `make demo-fixture`
  (`artifacts/demo_batch.json`).

**Rejected:** Supabase (more product than we need), Cloudflare D1 (backend is not on CF),
MongoDB (we have a relational audit trail; foreign keys are the point), and — as of this
revision — any deployed database at all, for the deploy target described above.

---

## LLM: **provider-agnostic adapter, default Google Gemini free tier**

- Used only for: root-cause narrative, Hinglish/multilingual nudge composition inside an
  approved compliance template, and natural-language Q&A over the audit log.
- **Never for money decisions.** Enforced by module boundary: `agent/decide.py` has no LLM
  import, and a test asserts it.
- **Every LLM output is cached to `artifacts/llm_cache/` and committed.** The repo runs
  end-to-end with **no API key**. This is a reproducibility requirement, not an optimisation.
- Behind `llm/provider.py` so Gemini / Groq / Anthropic / local are one-line swaps.

Chosen for the most generous free tier at time of writing. The adapter means being wrong
about that costs one file.

---

## Frontend: **Next.js 15 (App Router) + Tailwind + shadcn/ui + Recharts**

- Best visual quality per unit of build time. shadcn/ui provides a coherent design system
  we own the source of — no runtime dependency, no generic-template look.
- Recharts for the evidence charts; **the `dataviz` skill must be loaded before writing any
  chart code** — the metrics page is the most important screen in the video and must read
  as one designed system, with correct error bars and accessible colour.
- Dark, precise, monospace numerals. Razorpay-adjacent in seriousness, **never cloning
  their brand or logo** — impersonation would be a disqualifier.

---

## Tooling

| Tool | Why |
|---|---|
| `uv` | Fast, lockfile-based, reproducible Python envs |
| `ruff` | Lint + format in one, zero config drift |
| `mypy --strict` on `agent/` and `models/` | The money path is typed. Enforced in CI. |
| `pytest` + `hypothesis` | Property tests on the compliance gate: *no generated action ever violates a HARD rule* |
| `Makefile` | One command per task; `make demo` runs everything |
| GitHub Actions | ruff + mypy + pytest + smoke eval on every push. **A green CI badge on a hackathon repo is a real signal.** |
| `mermaid` in README + hand-built SVG | Architecture diagram is a submission requirement |

---

## Reproducibility contract (this is a judged property)

1. `git clone && make demo` works on a clean machine with **no API keys and no cloud account**.
2. Every random process takes an explicit seed; `make eval` is bit-for-bit reproducible.
3. Every simulator parameter carries a `source:` field; un-sourced ones are listed in the
   README as assumptions.
4. All reported numbers are regenerated by `make eval` into `artifacts/`, and the README
   quotes those files rather than hand-typed figures.
5. CI runs a reduced-seed `make eval` so the pipeline is proven working on every push.
