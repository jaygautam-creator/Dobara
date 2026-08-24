# 05 — Model Specification

**Rule: no LLM anywhere in this layer.** Money decisions run on tabular, calibrated,
inspectable models. A test asserts `models/` and `agent/decide.py` have no LLM import.

Tree ensembles deliberately mirror Razorpay's own published stack (Bygari et al., IEEE Big
Data 2021 — logistic regression for downtime, random forest for success probability,
adaptive time decay for real-time features).

---

## Model 1 — Recovery

`P(debit succeeds | context, attempt_time)`

**Estimator:** LightGBM binary classifier. Baseline for comparison: logistic regression —
**always report both.** If gradient boosting does not clearly beat the linear baseline,
report that honestly; it is a finding, not a failure.

**Features** (all strictly pre-decision; leakage-tested):

| Group | Features |
|---|---|
| Bank | `bank_id`, `bank_health_ewma`, `bank_health_changepoint`, `bank_dow_profile`, `is_bank_holiday` |
| Method | `method` (upi_autopay / card / nach / emandate), `method_x_bank_success_rate` |
| History (Tier 2) | `attempt_index`, `hours_since_last_attempt`, `prior_failures_this_cycle`, `consecutive_failed_cycles`, `mandate_success_rate_to_date`, `mandate_age_cycles` |
| Timing (Tier 3) | `day_of_month`, `is_month_start_window`, `is_mid_month_window`, `day_of_week`, `days_until_cycle_end` |
| Amount | `amount`, `amount_vs_afa_threshold`, `amount_vs_mandate_typical` |
| Cause | `prev_error_source`, `prev_error_step`, `prev_error_reason` |
| Declared (Tier 1) | `has_declared_preferred_day`, `days_from_declared_day` |

Explicitly absent: anything encoding an individual's balance or income (rule
`DPDP-MINIMISE`). A test asserts the feature list contains no banned name.

**Calibration is the priority, not AUC.** We multiply this probability by rupees, so being
*right about the number* matters more than ranking. Isotonic regression fitted on the
validation split. **Report Brier score and a reliability diagram alongside AUC/PR — and
lead with calibration in the README.** Most entrants will report AUC and stop; leading
with calibration signals you understand what the probability is *for*.

---

## Model 2 — Revocation Hazard

`P(mandate revoked within k days | attempts, contacts, history)`

**This is the model nobody else will build, and it is where the thesis lives.**

**Formulation:** discrete-time hazard on person-period data — one row per mandate per day
at risk, target = revoked that day. LightGBM on the expanded frame; convert to a survival
curve for the horizon.

**Features:** `failure_notifications_this_cycle`, `total_contacts_30d`,
`days_since_first_failure_this_cycle`, `consecutive_failed_cycles`, `mandate_age_cycles`,
`amount_vs_income_proxy_band` (cohort band, **not** individual), `method`,
`merchant_category`, `has_customer_engaged_with_notice`.

**The key learned relationship:** hazard rises with *failure-notification count*, not
merely with elapsed time. That is what makes attempts costly and what inverts the
aggressive-retry playbook.

**Calibration:** same treatment. Report the reliability diagram. Report the fitted marginal
hazard per additional failure notification as a headline number — it is the most
interpretable output the project produces and belongs in the video.

---

## Model 3 — Bank Health

EWMA of debit success per `(bank × method)` with an **adaptive decay rate** — decay
accelerates when recent variance rises, so a degrading bank is detected quickly while a
stable one is not over-reacted to. This is a direct echo of Razorpay's published dynamic
module, and the README should say so and cite the paper.

Plus a simple change-point flag (CUSUM or a rolling-window test) that feeds the
`ABSTAIN` path: **a bank in a detected regime change is a bank we do not trust our model on.**

Not learned end-to-end — a transparent statistical estimator, deliberately, so its
behaviour during an outage is explainable in the video.

---

## LTV estimator

`LTV_remaining = amount × expected_remaining_cycles × margin_factor`

Expected remaining cycles from the survival curve of *non-revoked* mandates by age and
category. Deliberately simple and transparent — it is a multiplier on the downside term
and an opaque LTV model would undermine the audit story. **Its assumption range goes into
the sensitivity analysis**, because the headline conclusion depends on it.

---

## Training protocol

1. Temporal split (train 1–4 / val 5 / test 6–8) + cold-start mandate holdout.
2. Fit on train; tune on val; **the test set is touched exactly once, at the end.** Record
   the number of times test was evaluated in `artifacts/summary.json` as an honesty marker.
3. Calibrate on val (isotonic).
4. Report on test: AUC, PR-AUC, **Brier**, reliability diagram, and per-slice metrics by
   bank / method / attempt index — including the **regime-shift bank reported separately**.
5. Persist with a `model_version` hash recorded in every audit line.
6. SHAP-style attribution retained per prediction and surfaced in the audit trail and UI.

## Honesty guardrails

- If a model does not beat its linear baseline, **say so in the README.**
- No metric is reported without a confidence interval.
- Slice metrics are mandatory; an aggregate number that hides a broken slice is a lie.
- If the recovery model's calibration is poor in a slice, the agent must `ABSTAIN` there —
  the policy is *required* to consume its own uncertainty estimate.
