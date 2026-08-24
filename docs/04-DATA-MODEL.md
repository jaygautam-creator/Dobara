# 04 — Data Model & Simulator Specification

## Why a simulator, stated up front

There is **no public dataset of failed payments with retry outcomes**. Processors do not
release it. A simulator is therefore forced — so we make the simulator the most rigorous
thing in the repo rather than its weakest point.

Three devices carry that:

1. **Every parameter carries a `source:` field.** `sim/params.yaml` is machine-checked: a
   parameter without a source must be declared in `assumptions:` and is auto-listed in the
   README under "Unsourced assumptions".
2. **Hidden latent state.** The customer's balance-availability process exists in the
   simulator and is *never* exposed to features. Without this the agent learns its own
   generator and the evaluation is circular. **This is the single most important design
   property of the whole project.**
3. **Sensitivity analysis + break-even reporting.** We report the parameter values at which
   our conclusion would flip. (See `docs/07-EVAL-SPEC.md`.)

## Calibration anchors (real, cited)

| Quantity | Value | Source |
|---|---|---|
| UPI technical decline (TD) | 8–10% (2016) → 0.7–0.8% (2025); NPCI target <1% | NPCI ecosystem statistics |
| UPI business decline (BD) | NPCI target <5% (circular OC-149, Jun 2022) | NPCI |
| Bank-wise TD/BD, uptime | Published monthly, per bank | NPCI BD/TD & Uptime page |
| AutoPay mandate revocations | **>20 million/month**, low balance | Business Standard |
| New AutoPay mandates | ~50M registered Jul 2025 (~2× YoY) | Business Standard |
| Mandate executions | 808M/month (Jul 2025), up from 392M | Business Standard |
| Involuntary churn share | 20–40% of total churn | Recurly / dunning benchmarks |
| Payment failure rate | ~4–6% B2B, 6–10% B2C | Dunning benchmarks |
| Dunning recovery rate | avg 30–45%; top quartile 55–70% | Dunning benchmarks |
| NACH SIP bounce charge | ₹250–₹750 + GST per failure | Business Today |
| AFA threshold | ₹15,000 (₹1,00,000 insurance/MF/CC) | RBI e-mandate framework |

> **BUILD TASK, DAY 1 — resolved 2026-08-25.** The press figures do conflict. Here is the
> pin, and the reasoning for picking one side.
>
> **Pinned:** new UPI AutoPay mandate **registrations** were **~50 million in July 2025**,
> up from ~26 million in July 2024 (NPCI data, via
> [Business Standard, Feb 2025 / Sep 2025](https://www.business-standard.com/finance/personal-finance/upi-autopay-growth-2025-overtakes-cards-payments-npci-125022000316_1.html)).
> Mandate **executions** (recurring debits actually run against existing mandates) were
> **~808 million in July 2025**, up from ~392 million in July 2024 — same source. Business
> decline across the top 50 banks on these executions averaged **~74%** that month, which
> is far above the general UPI BD figure and is itself evidence for this project's thesis:
> AutoPay debits fail disproportionately, because they run at bank-decided moments the
> customer did not initiate. Revocations (**>20 million/month**, low balance) are reported
> against this same base — Business Standard, Sep 2025.
>
> **Rejected:** "over 120 million AutoPay mandates created every month," which recurs
> across secondary fintech blogs (payment-gateway marketing pages, listicle roundups). It
> is never traced to a specific NPCI release, its month is unstated, and it is inconsistent
> about whether it means new mandates, active mandates, or monthly *executions* — three
> different quantities that should not share one number. The 50M/808M figures above are
> preferred because they are dated, paired with a same-source year-on-year comparison, and
> internally consistent (registrations < executions, as expected since one mandate executes
> repeatedly). **`sim/params.yaml` uses 50M new mandates/month and 808M executions/month.**
> NPCI's own live ecosystem-statistics page (`npci.org.in/what-we-do/upi/upi-ecosystem-statistics`)
> returns 403 to automated fetches, so it could not be cross-checked directly during this
> session — noted here rather than silently worked around; a judge with a browser can
> verify.

---

## Entities

```
Merchant(id, name, category, arpu_band, avg_ticket)
Customer(id, bank_id, segment, preferred_debit_day?, opted_out_flags)
Mandate(id, merchant_id, customer_id, method, amount, cycle_day,
        created_at, status, afa_threshold_applicable)
Cycle(id, mandate_id, cycle_index, due_date, status)
Attempt(id, cycle_id, attempt_index, scheduled_at, executed_at,
        outcome, error_source, error_step, error_reason, gateway_ref)
Notification(id, mandate_id, cycle_id, kind, channel, sent_at,
             template_id, contained_defer_option, customer_response?)
Revocation(id, mandate_id, revoked_at, trigger_attempt_id?)
Decision(id, cycle_id, decided_at, chosen_action, expected_net,
         model_versions, rejected_alternatives_json, clauses_json,
         rupee_math_json, stopping_reason?, confidence_interval_json)
BankHealthSnapshot(bank_id, method, as_of, ewma_success, decay_rate,
                   changepoint_flag, sample_n)
```

`Attempt.outcome` ∈ `{success, soft_decline, hard_decline, rejected_no_pdn}`.
The fourth value matters: **a retry lacking a valid pre-debit notification is rejected
outright at the rail, not soft-declined.** The simulator must model this, because it is
the mechanism that makes the aggressive arm expensive.

`error_source` / `error_step` / `error_reason` use **Razorpay's real error taxonomy**
(`source` ∈ customer / gateway / bank / network). Never invent a decline code.

---

## Latent (hidden from the agent — enforced by test)

```
CustomerLatent(customer_id, income_day, income_amount_dist,
               spend_process_params, balance_curve, revocation_propensity)
BankLatent(bank_id, base_td, base_bd, outage_schedule, dow_profile)
```

`features/` has **no import path** to these tables. A test asserts it.

---

## Simulator mechanics

**Time:** daily ticks over ~8 monthly cycles.

**Balance process:** each customer has a latent income day (salary-cycle clustered around
month start, plus a mid-month cohort) and a spend process. Balance-at-debit determines
insufficient-funds outcomes. **Day-of-month therefore genuinely matters** — and the agent
must *discover* this from Tier-2/Tier-3 evidence rather than being handed it.

**Bank behaviour:** per-bank TD/BD priors calibrated to NPCI ranges, a day-of-week profile,
and **correlated outage events** injected from real dated UPI outage occurrences. Outages
are the interesting hard case and the reason a static policy fails.

**Notification effect:** every attempt forces a pre-debit notification (rule `RBI-PDN-24H`).
Each *failure* notification increments the customer's revocation hazard. The population
revocation rate is calibrated so aggregate revocations match the ~20M/month ratio against
the mandate base.

**Revocation:** discrete-time hazard driven by failure-notification count, contact density,
consecutive failed cycles, mandate age, and latent propensity.

**Response to date-change offers:** low base response rate (single-digit %), configurable.
The system must perform well at a 0% response rate — Tier 1 is a bonus, not a dependency.
**Include a `response_rate: 0.0` run in the evaluation to prove this.**

---

## Splits — leakage is the failure mode

- **Temporal, by cycle.** Train cycles 1–4, validate 5, test 6–8. Never a random row split:
  cycles of the same mandate are correlated and a random split leaks.
- **Cold-start split.** Additionally hold out a set of mandates entirely unseen in training,
  to measure performance on new customers.
- **Regime shift, test-only.** One bank's failure profile changes materially in the test
  window only. The evaluation must punish memorisation. **Report performance on this bank
  separately** — this is where `ABSTAIN` should fire, and showing it firing is the
  graceful-failure demo.

## `sim/params.yaml` shape

```yaml
banks:
  HDFC:
    base_td: {value: 0.008, source: "https://www.npci.org.in/.../upi-ecosystem-statistics"}
    base_bd: {value: 0.041, source: "NPCI OC-149 target <5%; calibrated within range"}
revocation:
  hazard_per_failure_notification:
    value: 0.031
    source: "assumption; calibrated so population revocation matches 20M/month ratio"
    assumption: true
    sensitivity_range: [0.015, 0.060]
```

Any entry with `assumption: true` is auto-collected into the README's assumptions table
along with its `sensitivity_range`. **A parameter with neither a source nor an assumption
flag fails `make check`.**
