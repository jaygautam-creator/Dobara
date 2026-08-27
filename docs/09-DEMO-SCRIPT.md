# 09 — Five-Minute Pitch Video

Structure is fixed; wording is refined on the day. Record after `make eval` has produced
final numbers so every figure spoken aloud matches `artifacts/summary.json`.

| Time | Beat | Content |
|---|---|---|
| 0:00–0:30 | **The hook** | "Twenty million UPI AutoPay mandates are revoked in India every month, because the customer didn't have the balance when the debit ran. The failed debit isn't the loss. It's the trigger." |
| 0:30–1:10 | **The mechanism** | The regulatory fact. Every retry in India legally requires its own 24-hour pre-debit notification; retries that skip it are rejected outright, not soft-declined. So eight retries is eight mandatory messages. "The Western dunning playbook is, under Indian regulation, a legally-mandated harassment machine." |
| 1:10–1:30 | **The thesis** | "Every retry is a bet with downside. Dobara prices that bet." Motto on screen. |
| 1:30–2:30 | **Live demo** | Control Room, batch running against Razorpay test mode. Counters climbing — including **attempts not made**. |
| 2:30–3:20 | **One case, opened** | `/audit/89`, scrolled to **cycle 6** — not whatever the Control Room's default active case shows. Verified against `artifacts/demo_batch.json`: the first-cycle decision for every mandate in the demo batch is dominated by generic "N candidates tied at this E[net]" rows, which don't visibly support the "retrying twice scores negative" line. Mandate #89 cycle 6 is the one case in the fixture whose rejected alternatives include a concrete, named negative-E[net] retry ("retry via whatsapp", −₹985) — pin that scroll position before recording. Both calibrated probabilities with CIs, the rupee arithmetic term by term, compliance clauses lighting green. |
| 3:20–3:50 | **Graceful failure** | `/audit/144`, scrolled to **cycle 7–8** — mandate #144 is a `regime_shift_bank` case, but cycles 1–6 still show ordinary `schedule_debit`; the abstain (`stopping_reason: insufficient_confidence`) only appears at cycle 7. Landing on an earlier cycle undercuts the beat. The agent detects the change-point, abstains, names the reason, and **stops** — it does not fall back to a guessed attempt (CLAUDE.md: "when in doubt, the agent stops"; `docs/DECISIONS.md` [2026-08-25] "Abstain must stop, not fall back to an attempt" overrules this doc's original fall-back design). "It doesn't guess. It says it doesn't know." |
| 3:50–4:40 | **The evidence** | `/evidence`. **Overrun risk, flagged by rough take, confirm with a stopwatch before cutting anything**: reading the on-screen numbers aloud (headline card, five-arm table, break-even statement, scope-of-applicability line) runs ~70–90s at natural pace — this beat may not fit in 50s as scripted. The **five-arm table stays in the spoken pass** — it's the one frame where a judge sees the whole argument at once (dobara recovers less gross, more net LTV, CI on every cell) and narrating over it silently would waste the only moment we get for the differentiator. Instead, cut the **rerun-provenance paragraph** and the **credibility-anchor box** from speech — both stay visible on screen, unnarrated; a judge who cares pauses to read them, one who doesn't won't miss them. If it still runs long after that cut, the fix is changing the page (e.g. moving the rerun paragraph off this page, or extending this beat and trimming elsewhere), not silently dropping the five-arm table. Content, unchanged: Five arms with 95% CIs. **The money chart** — not the crossover we expected when we wrote this script: `aggressive_8x` never has a honeymoon. It loses on net LTV from **cycle 1**, because in India the cost lands immediately — every retry is a legally mandated notification. And past cycle 4 it loses on **gross** recovery too, underperforming even the metric it exists to maximise, because it burns mandates faster than it collects from them. The break-even statement, both directions: `dobara` beats `aggressive_8x` across the entire declared hazard range, but only beats `razorpay_default` above hazard≈0.074 — against a calibrated, NPCI-anchored value of 0.098, a real but not enormous margin. **Scope of applicability**: this needs roughly 48%+ gross margin on subscription revenue to hold — built for OTT, SaaS, insurance, memberships, not thin-margin recurring billing. Calibration led before AUC. |
| 4:40–5:00 | **Close** | Architecture in one frame. Then **what we deliberately did not build**: no individual cash-flow inference, no probing debits, no LLM on the money path. "The agent's best outcome is making itself unnecessary for that customer." |

## Rules for the recording

- **Say the honest numbers out loud**, CIs included. If a result is not significant, say so.
- Say the data is simulated, and say why (no public dataset exists), and say what it is
  calibrated against — inside the first two minutes, not buried at the end.
- Never claim a licence, partnership, or endorsement. Say "Razorpay test mode" explicitly.
- Show the CI green badge and the property test that proves the compliance gate holds.
- Screen recording at 1080p minimum; readable font sizes; no dead air while things load —
  pre-warm the demo.
- **Pre-select the cases before recording** (see the case picks above) — do not let the
  Control Room's default active case or an arbitrary regime-shift mandate stand in for
  the beat; the fixture's cases are not interchangeable and the wrong one visibly
  contradicts the line being spoken over it.

## Rough-take findings (27 Aug 2026, against https://dobara-one.vercel.app)

A throwaway pass — headless renders of each beat's target page at 1920×1080 plus word-count
timing against this script, not an actual recorded/narrated take (the in-session browser
extension was unresponsive). Findings that changed the script above are not repeated here.

- **Landing page already covers 0:00–1:30 in one screen, in script order** — hook stat cards,
  the failed-debit-is-the-trigger paragraph, the objective-function callout. No change
  needed; this page should open the recording exactly as planned.
- **The Control Room's "rejected alternatives" list is mostly noise at video bitrate**: rows
  read as repeated `N candidates tied at this E[net]` lines rather than nameable retry
  options. Legible in a static screenshot, but will read as clutter under a moving cursor.
  Fix: **collapse tied rows behind an expandable count** (`9 candidates tied at ₹5,105 ▸`),
  not dimming — the ties were surfaced deliberately after the audit trail was found
  misrepresenting them as reasoned rejections, so hiding them via opacity would partly undo
  that fix. Collapsing keeps the information present and honest while removing the clutter.
- **Theme toggle and the `/audit` "ask why" box are still unbuilt** — neither is referenced by
  any scripted beat, so their absence doesn't block a recording today, but they should land
  before the final take since a judge who clicks around outside the narrated path will hit
  their absence.
- **Not yet verified by an actual spoken pass**: audio pacing, whether the Control Room's
  streaming-reveal animation (150 cases at 45ms/case ≈ 6.75s) is worth showing at full speed
  on camera, and whether 5 minutes holds once beats are re-timed per the notes above. Do one
  real recorded pass once the case picks and the `/evidence` narration cut are locked in.
