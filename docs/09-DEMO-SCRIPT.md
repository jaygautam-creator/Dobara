# 09 — Five-Minute Pitch Video

Structure is fixed; wording is refined on the day. Record after `make eval` has produced
final numbers so every figure spoken aloud matches `artifacts/summary.json`.

| Time | Beat | Content |
|---|---|---|
| 0:00–0:30 | **The hook** | "Twenty million UPI AutoPay mandates are revoked in India every month, because the customer didn't have the balance when the debit ran. The failed debit isn't the loss. It's the trigger." |
| 0:30–1:10 | **The mechanism** | The regulatory fact. Every retry in India legally requires its own 24-hour pre-debit notification; retries that skip it are rejected outright, not soft-declined. So eight retries is eight mandatory messages. "The Western dunning playbook is, under Indian regulation, a legally-mandated harassment machine." |
| 1:10–1:30 | **The thesis** | "Every retry is a bet with downside. Dobara prices that bet." Motto on screen. |
| 1:30–2:30 | **Live demo** | Control Room, batch running against Razorpay test mode. Counters climbing — including **attempts not made**. |
| 2:30–3:20 | **One case, opened** | The decision card. Both calibrated probabilities with CIs. The rupee arithmetic term by term. **The rejected alternatives** — "retrying twice scores negative; the second notice costs more in revocation risk than it can recover." Compliance clauses lighting green. |
| 3:20–3:50 | **Graceful failure** | The regime-shift bank. The agent detects the change-point, abstains, names the reason, and **stops** — it does not fall back to a guessed attempt (CLAUDE.md: "when in doubt, the agent stops"; `docs/DECISIONS.md` [2026-08-25] "Abstain must stop, not fall back to an attempt" overrules this doc's original fall-back design). "It doesn't guess. It says it doesn't know." |
| 3:50–4:40 | **The evidence** | `/evidence`. Five arms with 95% CIs. **The money chart** — not the crossover we expected when we wrote this script: `aggressive_8x` never has a honeymoon. It loses on net LTV from **cycle 1**, because in India the cost lands immediately — every retry is a legally mandated notification. And past cycle 4 it loses on **gross** recovery too, underperforming even the metric it exists to maximise, because it burns mandates faster than it collects from them. The break-even statement, both directions: `dobara` beats `aggressive_8x` across the entire declared hazard range, but only beats `razorpay_default` above hazard≈0.074 — against a calibrated, NPCI-anchored value of 0.098, a real but not enormous margin. Calibration led before AUC. |
| 4:40–5:00 | **Close** | Architecture in one frame. Then **what we deliberately did not build**: no individual cash-flow inference, no probing debits, no LLM on the money path. "The agent's best outcome is making itself unnecessary for that customer." |

## Rules for the recording

- **Say the honest numbers out loud**, CIs included. If a result is not significant, say so.
- Say the data is simulated, and say why (no public dataset exists), and say what it is
  calibrated against — inside the first two minutes, not buried at the end.
- Never claim a licence, partnership, or endorsement. Say "Razorpay test mode" explicitly.
- Show the CI green badge and the property test that proves the compliance gate holds.
- Screen recording at 1080p minimum; readable font sizes; no dead air while things load —
  pre-warm the demo.
