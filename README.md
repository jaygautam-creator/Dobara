<h1>Dobara <sub><sup>दोबारा</sup></sub></h1>

**Recover the payment. Keep the mandate.**

An AI revenue-recovery agent for Indian recurring payments.
Submission for the **Razorpay AI Buildathon — Track 03: AI Revenue Recovery**.

> ⚠️ **Status: in development.** Metrics below are placeholders until `make eval` runs.
> No number appears in this README that is not read from `artifacts/summary.json`.

---

## The problem

> **More than 20 million UPI AutoPay mandates are revoked every month in India** because
> the customer's account lacked balance when the debit ran.
> — [Business Standard](https://www.business-standard.com/finance/news/upi-autopay-revocations-hit-20-mn-monthly-over-low-customer-balances-125090700500_1.html)

The failed debit is not the loss. **It is the trigger.** Debit fails → customer is
notified → customer opens their UPI app and kills the mandate → the merchant loses not
this month's ₹499 but every future ₹499.

## The mechanism nobody prices

> **In India a retry requires its own fresh 24-hour pre-debit notification. Retries that
> skip it are rejected outright at the rail — not soft-declined.**

So you cannot retry silently. You cannot retry faster than 24 hours. And **eight retries
means eight mandatory messages** telling a customer that this merchant keeps failing to
take their money.

The standard dunning playbook — retry aggressively, up to eight attempts — is, under Indian
regulation, **a legally-mandated harassment machine**. The regulator forced the retry to be
loud and nobody redesigned the strategy around it.

### Therefore

> **Every retry is a bet with downside. Retrying harder can lose more money than not
> retrying at all.**

Dobara prices that bet:

```
E[net | action] = P(success | t) × amount
                − P(revoke | attempts+1, contacts) × LTV_remaining
                − cost(channel)
```

It acts on the argmax, and **stops when the expression goes negative** — a stopping rule
with a rupee behind it rather than an arbitrary attempt cap.

---

## What it does

**① Detects** revenue at risk — bank-health monitoring with adaptive time decay, plus
pre-debit risk scoring, producing a ranked queue with rupees attached *before* anything fails.

**② Determines** the intervention — root-cause classification over Razorpay's real error
taxonomy, then a policy over a bounded action set scored on expected net lifetime value.

**③ Executes** a bounded workflow — every action passes a declarative compliance gate whose
rules carry their citations; nothing above the sign-off threshold runs autonomously.

**④ Measures** — five arms, thirty seeds, paired confidence intervals, sensitivity analysis,
and a stated break-even condition under which our conclusion would flip.

---

## Honest metrics

*(populated by `make eval` — every figure below is read from `artifacts/summary.json`)*

| Arm | Gross ₹ recovered | Net LTV Δ | Attempts | Notifications | Revocations |
|---|---|---|---|---|---|
| `do_nothing` | — | — | — | — | — |
| `razorpay_default` | — | — | — | — | — |
| `aggressive_8x` | — | — | — | — | — |
| **`dobara`** | — | — | — | — | — |
| `oracle` | — | — | — | — | — |

All values ± 95% CI over 30 seeds. Paired comparisons on identical seeds.

**The headline is not gross recovery.** The `aggressive_8x` arm is expected to beat us on
gross while losing on net lifetime value. That crossover is the result.

**Calibration is reported before AUC.** These probabilities get multiplied by rupees, so
being right about the number matters more than ranking. Brier scores and reliability
diagrams for both models are in `/evidence`.

**Credibility anchor:** Razorpay's own production routing system reports a
[4–6% success-rate lift](https://arxiv.org/abs/2111.00783) across millions of real
transactions. If our headline number looks enormous, we have a bug.

---

## Honesty statement

**The data is simulated, and here is why.** No public dataset of failed payments with retry
outcomes exists — processors do not release it. So we built a simulator whose every
parameter carries a `source:` field pointing at NPCI decline statistics, RBI e-mandate
rules, Razorpay's published documentation, or a declared assumption with a sensitivity
range. Parameters we could not source are listed in the assumptions table below.

Critically, **the simulator holds latent state the agent can never observe** — each
customer's balance process is hidden from every feature, enforced by test. Without that,
the agent would learn its own generator and the evaluation would be circular.

The test set is touched once. The evaluation count is recorded in `artifacts/summary.json`.

### Circularity and what our numbers can and cannot show

We caught ourselves making exactly the mistake the paragraph above exists to prevent, and
we're naming it here rather than letting a reviewer find it first.

The revocation hazard model's headline result — predicted hazard rising 0.113 → 0.130 →
0.207 as same-cycle failure count goes 0 → 1 → 2 — **does not empirically confirm the
thesis.** `sim/params.yaml`'s `revocation.hazard_per_failure_notification` is a declared
`assumption` (recalibrated 2026-08-25 against the revocations/execution target ratio
below). The rising-hazard-with-failures relationship was authored into the simulator by
hand. The hazard model recovering it is not evidence about the world — it's evidence that
the model is correctly specified and can recover a known relationship from data. That's a
real and useful result, but it validates the *model*, not the *thesis*.

**What the result actually shows:** the hazard model works as intended — discrete-time,
calibrated, and able to recover a planted signal cleanly.

**What actually supports the thesis** — none of it a fitted parameter:

1. **The regulatory mechanism.** Every retry legally requires its own fresh 24-hour
   pre-debit notification (`docs/01-REGULATORY.md`, RBI-PDN-24H). Retry volume mechanically
   drives notification volume; this is a rule, not a model output.
2. **The published NPCI figures.** ~20 million AutoPay revocations against ~808 million
   executions per month (Business Standard, 2025, pinned in
   [`docs/04-DATA-MODEL.md`](docs/04-DATA-MODEL.md#calibration-anchors-real-cited)).
3. **Those revocations are attributed, in the source, to low customer balance** — the
   population a harassment-driven retry strategy is most likely to push over the edge.

**The defensible empirical claim**, to be established in Phase 4 rather than assumed here:
across the *full* declared `sensitivity_range` [0.05, 0.15] of
`hazard_per_failure_notification`, Dobara beats the `aggressive_8x` arm on net lifetime
value — plus the break-even value of that parameter below which `aggressive_8x` would win
instead. That comparison is falsifiable by construction: it's checked across the whole
plausible range of the one assumption doing the work, not at the single value we happened
to calibrate to, and it states the point at which our claim stops holding.

**A concrete example of how we handle a sourcing conflict.** Press coverage disagrees on
AutoPay volume: one recurring figure is "over 120 million mandates created every month,"
another is "50 million new mandates in July 2025." We pinned the latter — 50M new
registrations / 808M executions, July 2025, NPCI data via Business Standard, dated and
paired with a same-source year-on-year comparison — and rejected the 120M figure because
no source traces it to a specific NPCI release or states whether it means new mandates,
active mandates, or monthly executions. Full reasoning in
[`docs/04-DATA-MODEL.md`](docs/04-DATA-MODEL.md#calibration-anchors-real-cited).

---

## What Dobara deliberately does not do

- **No individual cash-flow inference.** We never model a specific person's balance or
  income. Only declared preference, our own transaction history, and aggregate cohort
  priors. We could have built the balance model. We chose not to. This is a **stated
  commitment**, held up by two different mechanisms: import isolation (`features/` has no
  import path to the simulator's hidden balance process, `sim/latent.py`, enforced by a
  test) and a name-based guard (`assert_no_banned_features` in `features/recovery.py`
  rejects any feature column whose name contains `balance`/`income`/`spend`/etc.). The
  name-based guard catches naming, not semantics — it cannot detect a differently-named
  feature that is *functionally* a balance proxy. It is a backstop and a stated
  commitment, not a proof; the real guarantee is the import boundary plus review.
- **No probing debits.** A ₹1 test debit to detect whether funds exist is technically
  clever, ethically indefensible, and almost certainly breaches the mandate's amount terms.
- **No LLM on the money path.** Probabilities and decisions are tabular, calibrated and
  inspectable. LLMs handle narrative, language and explanation only — enforced by an import
  boundary and a test.
- **No funds handled.** Dobara proposes; a licensed payment aggregator executes.

---

## Compliance

Regulatory rules are implemented as **declarative, cited, structurally-enforced
constraints** — not a paragraph claiming compliance. A `hypothesis` property test asserts
that no generated action can violate a HARD rule.

Mapped to RBI's **FREE-AI** framework (13 Aug 2025) Sutra by Sutra — safety, transparency,
accountability, fairness, inclusivity, sustainability, explainability. Full detail and the
rule table in [`docs/01-REGULATORY.md`](docs/01-REGULATORY.md).

*Not legal advice. Engineering research from public sources. Where a rule is genuinely
ambiguous we take the stricter reading and flag it.*

---

## Run it

```bash
git clone <repo> && cd dobara
make setup
make demo     # sim → train → eval → api + web
```

Works on a clean machine with **no API keys and no cloud account**. LLM outputs are cached
and committed; the deployed demo serves committed artifacts.

## Documentation

| | |
|---|---|
| [Thesis](docs/00-THESIS.md) | Why this project, and the insight |
| [Regulatory](docs/01-REGULATORY.md) | Legal clearance; rules as executable spec |
| [Architecture](docs/02-ARCHITECTURE.md) | System design and module contracts |
| [Tech stack](docs/03-TECH-STACK.md) | Every choice, and what was rejected |
| [Data model](docs/04-DATA-MODEL.md) | Schemas and simulator specification |
| [Models](docs/05-ML-SPEC.md) | Features, training, calibration |
| [Agent](docs/06-AGENT-SPEC.md) | Decision layer, compliance gate, audit |
| [Evaluation](docs/07-EVAL-SPEC.md) | Arms, CIs, sensitivity, break-even |

---

*Built for the Razorpay AI Buildathon. Uses Razorpay **test mode** only. Not affiliated
with or endorsed by Razorpay.*
