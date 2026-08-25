# 06 — Agent Decision Layer

`agent/decide.py` is a **pure function**: no I/O, no network, no LLM, no clock. Everything
it needs arrives in `DecisionContext`. This makes the money path exhaustively unit-testable
and property-testable, which is the point.

## Signature

```python
def decide(ctx: DecisionContext, models: ModelBundle, config: PolicyConfig) -> Decision
```

`Decision` **always** carries, whatever the outcome:

```python
chosen: Action
expected_net: Money
# Wilson-interval approximation, not an eval CI — see docs/DECISIONS.md [2026-08-25]
confidence_band: tuple[Money, Money]
rejected_alternatives: list[RejectedAlternative]  # each with its own E[net] and reason
clauses_satisfied: list[ClauseRef]
clauses_blocked: list[ClauseRef]
rupee_math: RupeeMath  # every term, shown
model_versions: dict[str, str]
feature_attribution: dict[str, float]
stopping_reason: StoppingReason | None
```

**`rejected_alternatives` is the differentiator in the audit trail.** Anyone can log what
they did. Logging what you *considered and declined, with the arithmetic*, is what makes a
trail auditable rather than decorative.

## Candidate generation

For each case, enumerate the legal candidate space:

1. Candidate times `t` across the remaining legal window, floored at `now + 24h` (rule
   `RBI-PDN-24H`) and capped at cycle end.
2. Candidate channels for the mandated notification (SMS via DLT template / WhatsApp
   utility template / email).
3. `OFFER_DATE_CHANGE` if the converge rule permits it this cycle.
4. `STOP` and `ESCALATE_TO_HUMAN` are always in the candidate set.

Score each, take the argmax, subject to the gate and the positivity floor.

## The compliance gate

`agent/compliance.py`. Declarative rules, each an object:

```python
Rule(
    id="RBI-PDN-24H",
    text="Every debit attempt, including every retry, must be preceded by a "
    "pre-debit notification at least 24 hours earlier.",
    severity=HARD,
    citation="RBI e-mandate framework",
    source_url="https://...",
    predicate=lambda action, ctx: ...,
)
```

**Structural enforcement, not advisory.** The gate runs *inside* candidate generation, so a
non-compliant action is never constructed. A `hypothesis` property test asserts:

> for any generated `DecisionContext`, `decide()` never returns an action violating a HARD rule.

That test in CI is the proof of the "bounded" claim in the brief, and it is worth showing
on screen in the video.

Every blocked candidate is recorded in `clauses_blocked` — so the audit trail shows the
regulation actively shaping behaviour, not merely being claimed.

## Human sign-off

Above `config.human_signoff_threshold_inr`, or whenever `ESCALATE_TO_HUMAN` is chosen, the
action is emitted as a **proposal requiring approval** and appears in the Control Room's
approval queue. Nothing above the threshold executes autonomously. This is the "bounded,
gated" language from the brief, made literal.

## Abstention — the graceful failure

`ABSTAIN` fires when any of:

- The `(bank, method)` slice has fewer than `config.min_slice_n` observations
- Bank health shows a detected change-point (our model's assumptions no longer hold)
- Calibration error in this slice exceeds `config.max_slice_brier`
- The CI on `E[net]` for the best action straddles zero

On abstention the agent **falls back to Razorpay's documented default policy and says so in
plain language.** It does not guess. The demo deliberately includes a case where this
fires — the regime-shift bank in the test window is exactly that case.

> This satisfies the brief's requirement for a failure the agent handles gracefully, and it
> is a stronger version of it: the failure is *designed, detected, named, and measured*
> (abstention count is a reported metric).

## Audit trail

Append-only. Never mutated. One row per decision plus one row per executed action.

Human-readable rendering, generated from the structured record:

```
[2026-08-28 09:14:02 IST]  mandate mnd_8813  cycle 6  attempt 2
  SAW    upi_autopay · HDFC · ₹499 · prev: customer/payment_authorization/insufficient_funds
         bank_health_ewma 0.971 (stable, n=2,140) · day_of_month 28 · attempt_index 2
         notifications_this_cycle 1 · consecutive_failed_cycles 0 · mandate_age 6
  THOUGHT P(success | 2 Sep 10:00) = 0.71 [0.66–0.76]   (isotonic-calibrated)
          P(revoke | this attempt fails) = 0.131   (hazard model's raw output — a
            conditional probability; NOT used directly, see below)
          P(revoke) = (1 − 0.71) × 0.131 = 0.038 [0.029–0.049]   (weighted by P(fail),
            since the candidate hasn't failed yet — the model's raw output on its own
            would overstate this ~3.4×)
          LTV_remaining = ₹4,240
          E[net] = 0.71×499 − 0.038×4240 − 0.35 = ₹193.2  [₹151.8 – ₹231.6]
  ALT     retry 29 Aug 10:00 → E[net] ₹41.7   (lower P(success): pre-salary window)
          retry twice (29 Aug + 2 Sep) → E[net] −₹18.4  (second notice raises hazard above gain)
          stop now → E[net] ₹0
  GATE    ✓ RBI-PDN-24H (notice scheduled 1 Sep 10:00)  ✓ CONDUCT-HOURS  ✓ TRAI-DLT
          ✓ RBI-AFA-15K (₹499 < ₹15,000)  ✓ DOBARA-FATIGUE (1 of 2 used)
  DID     SEND_PRE_DEBIT_NOTICE(1 Sep 10:00, whatsapp, tmpl_pdn_defer_v3)
          SCHEDULE_DEBIT(2 Sep 10:00)   [proposal → rzp test mode]
  WHY     "Two failed cycles have not occurred; the customer's successful debits cluster
           after month-start. One well-placed attempt on 2 Sep is worth ₹193 more than
           retrying tomorrow, and materially more than retrying twice — the second notice
           would cost more in revocation risk than it could recover."
```

That block is a slide in the pitch video.

## Policy configuration

Everything tunable lives in `config/policy.yaml` with a stated rationale per value — no
magic numbers in code. Includes: `max_attempts_per_cycle`, `max_notifications_per_cycle`,
`cost_cap_inr`, `human_signoff_threshold_inr`, `min_slice_n`, `max_slice_brier`,
`holdout_fraction`, `retry_requires_fresh_pdn`, `converge_min_cycles_between_date_changes`.
