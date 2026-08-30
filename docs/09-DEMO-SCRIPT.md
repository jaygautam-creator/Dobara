# 09 — Five-Minute Pitch Video

> Rewritten 2026-08-28 against the post-redesign site (`docs/10-REDESIGN.md`, Sessions
> A–F, commits `ad1e671`…`05b6ffb`). The previous version of this script was written
> before the redesign and referenced screens, routes and layouts that no longer exist
> (a wrap-container `/mandate/[id]`, a paragraph-only `/`, no `/architecture`). This
> version is written against the actual site.

Structure is fixed; wording is refined on the day. Record after `make eval` has
produced final numbers so every figure spoken aloud matches `artifacts/summary.json`,
and record against the pushed deploy, not `localhost` — what a judge can click on
after the video is what should be on screen during it.

## Shot list

| Time | Beat | Route / shot | Say |
|---|---|---|---|
| 0:00–0:45 | **The hook + the mechanism** | `/` — hero, then scroll to the three-fact band (20M / 24h / 8×) | "Twenty million UPI AutoPay mandates are revoked in India every month — not because customers don't want to pay, but because the debit failed and the merchant kept retrying. Here's why that's worse than it sounds: Indian regulation requires every retry on a mandate to carry its own 24-hour pre-debit notification. No exceptions, no silent retry. So the standard dunning playbook — retry, retry, retry, up to eight times — is, under Indian law, a mandated stream of messages telling a customer their merchant keeps failing to take their money." |
| 0:45–1:05 | **The thesis** | `/` — hero line + motto, on screen already from 0:00 | "Every retry is a bet against the mandate surviving. Dobara prices that bet, and knows when to stop." (Read the motto off the page: *"Recover the payment. Keep the mandate."*) |
| 1:05–2:00 | **The demonstration** | `/` — scroll to the two-lane demonstration (`components/home/Demonstration.tsx`) | Let the aggressive lane fire its notifications on screen, one beat at a time, into the revocation event and the greyed-out lane. Then the Dobara lane. "Same mandate, same simulated customer, same clock — one policy keeps retrying past the point of no return, the other one doesn't." **Check the actual numbers on screen before speaking them — they are case-specific, not a fixed script.** As of 2026-08-30's `artifacts/home_demo.json` (mandate 4838, seed 301) the shown case is: aggressive fires 5 notifications, gets 0 successful debits, and the mandate is revoked at cycle 1 (₹1,460.93 LTV lost); Dobara fires 8 notifications spread across the mandate's life, gets 6 successful debits, and the mandate survives (never revoked, ₹0 LTV lost). Dobara sends *more* notifications here, not fewer — the point isn't "always retry less," it's "keep retrying exactly as long as the bet stays positive, and no further." Say the real counts, not an illustrative "8 vs 2." Read the caption's own honesty line aloud: this is the **median** case across the candidate set the aggressive policy lost and Dobara kept, not the best one — advantage on this set runs from the p25 to p75 figures shown, CIs included. Do not round past what the page states. |
| 2:00–2:50 | **Live case, opened** | `/control-room` briefly (batch counters, "attempts not made" as the `feature` tile), then `/audit/89` scrolled to **cycle 6, second attempt (2026-06-03)** | On Control Room: point at the **attempts not made** counter — "that's the thesis counter, not a vanity metric: it's Dobara declining to send a notification it calculated wasn't worth the mandate risk." Open mandate #89, scroll to cycle 6's *second* attempt — the chosen action there is `stop` (`stop_reason: negative_expected_value`), and the rejected-alternatives list names a concrete losing option, `retry via whatsapp`, scored **−₹715.67** — lower by ₹715.67 than the chosen candidate (0), not a wall of tied candidates. Walk the SAW → THOUGHT → ALT → GATE → DID → WHY grid left to right: what the agent saw, the calibrated probabilities with CIs, the rejected alternative and why it scored negative, the compliance clauses lighting green, the worked rupee equation with this decision's real numbers substituted in, the `stop` action taken. **Re-verify the exact rupee figure against the live page before recording** — read from `artifacts/demo_batch.json`'s `audit_by_mandate["89"]`, cycle 6, attempt 2 at the time of this rewrite (2026-08-30); it moves if the fixture regenerates. |
| 2:50–3:20 | **Graceful failure** | `/audit/144`, scrolled to **cycle 7** | Mandate #144 is bank `SBI` (a `regime_shift_bank` case); cycles 1–6 are ordinary `schedule_debit` decisions, and the agent **abstains at cycle 7 and again at cycle 8** — `abstain_reason: bank_health_changepoint`, not `insufficient_confidence` (corrected 2026-08-30 against `artifacts/demo_batch.json`; the reason enum member is `agent.actions.AbstainReason.BANK_HEALTH_CHANGEPOINT`). Land on cycle 7, the first abstain. "When the bank-health monitor flags a real shift in this bank's behaviour and the model can't yet trust its own calibration there, the agent doesn't guess and it doesn't fall back to an attempt. It stops and says why." |
| 3:20–4:20 | **The evidence** | `/evidence` — headline `hero` stat, the five-arm table, the money chart, the break-even statement | Read the headline stat with its CI. On the five-arm table: "Dobara doesn't recover the most gross rupees — the aggressive arm does, for a while. It recovers the most **net** lifetime value, because it isn't paying for that gross with mandates it destroys." On the money chart: aggressive_8x loses on net LTV from cycle 1 — the cost of a mandated notification lands immediately, win or lose the attempt — and past cycle 4 it loses on gross recovery too, because it burns mandates faster than it collects from them. State the break-even result both directions, with the numbers on screen — check `/evidence` at record time, since this has moved: as of 2026-08-30's `artifacts/sensitivity.json`, `dobara` beats `aggressive_8x` at every tested hazard point in the declared range [0.05, 0.15] — no break-even found there. Against `razorpay_default`, nothing inverts inside the declared range either, but the extended search past it *does* find one: widening the hazard parameter down toward its physical floor (0), the break-even is **hazard ≈ 0.0371**, against a calibrated value of **0.098** — a **2.64×** margin. Say it that way: not "no break-even exists," but "the located break-even sits well outside the plausible range, and at it `razorpay_default`'s own revocation ratio would have to run at ≈1.23%, roughly half NPCI's published ≈2.5%, for `dobara` to lose." Re-verify the exact figures against whatever `/evidence` shows on the day of recording, since these move with `make eval` / `python -m eval.sensitivity` reruns. Do **not** state a required minimum gross-margin figure — the earlier ≈48% claim was retracted after a later artifact regeneration and `/evidence` no longer states one; if asked, say built for OTT, SaaS, insurance, memberships — subscription businesses with real margin per mandate — not thin-margin recurring billing, without naming a threshold the evidence doesn't currently support. |
| 4:20–4:50 | **The architecture / what we didn't build** | `/architecture` — the LLM-boundary diagram, the compliance gate sequence | "Money decisions never pass through a language model — that's not a policy, it's a wall a test enforces; the LLM only narrates, on the other side. Every candidate action is generated, then the compliance gate removes anything that would breach an RBI, TRAI or NPCI rule, before anything gets scored." Then, spoken directly: what we deliberately did not build — no individual cash-flow inference, no probing debits, no LLM anywhere near the money path. |
| 4:50–5:00 | **Close** | `/` or `/architecture`, hold on the motto | "The agent's best outcome is making itself unnecessary for that customer. Recover the payment. Keep the mandate." |

Total: 5:00. The demonstration (1:05–2:00) is the single highest-value asset on the
site per `docs/10-REDESIGN.md` §4 and gets the most air time of any beat after the
hook.

## Rules for the recording

- **Say the honest numbers out loud, CIs included.** Every figure spoken must be one
  the page displays at that moment — no number is narrated from memory or from this
  script's draft values. If a result is not statistically significant, say so.
- Say the data is simulated, why (no public dataset of Indian AutoPay mandate outcomes
  exists), and what it's calibrated against — inside the first 90 seconds, not buried
  at the end. The three-fact band and the demonstration's caption both carry sourcing;
  read at least one source aloud.
- Never claim a licence, partnership, or endorsement with Razorpay or any bank/NPCI.
- Screen recording at 1080p minimum, readable font sizes, no dead air while things
  load — pre-warm every route before recording (visit each once so build-time data and
  fonts are cached).
- **Pre-select and pre-scroll every case before recording** — `/audit/89` to cycle 6,
  `/audit/144` to cycle 7–8. Do not rely on Control Room's default active case or an
  arbitrary regime-shift mandate; the fixture's cases are not interchangeable and the
  wrong one visibly contradicts the line spoken over it.
- Control Room's streaming reveal is click-to-skip (`docs/10-REDESIGN.md` §4) — use
  that; never make a judge, or this recording, wait through it at full speed.
- Record in one theme — **light, the site's default as of 2026-08-30** (a judge lands
  on light regardless of OS setting; see `docs/DECISIONS.md`) — do not toggle themes
  mid-recording, it adds nothing to the pitch.

## What the site cannot currently do (flagged, not scripted around)

- **No live batch run against Razorpay test mode.** `docs/10-REDESIGN.md`'s hard
  constraint is `output: "export"` — a static site reading pre-baked
  `artifacts/*.json`, with no server runtime, no API route, no live request at
  request time (see `docs/DECISIONS.md` [2026-08-26] "Data-shipping architecture").
  The original script's 1:30–2:30 beat ("Control Room, batch running against Razorpay
  test mode") describes a capability that does not exist on the deployed site and was
  cut, not narrated around. What Control Room shows is a real, recorded batch replayed
  client-side — say exactly that, not "live."
- **No compliance-gate property test shown on screen.** The original script's "show
  the property test that proves the compliance gate holds" beat has no corresponding
  UI — the property test lives in the Python test suite, not the frontend. The
  `/architecture` compliance-gate sequence shows the gate's structure and real rule
  set (`artifacts/compliance_rules.json`); it does not show a test run. Say the gate is
  structural and enforced by a test in the repo, but do not stage a test run that
  doesn't exist on-site.
- **Theme toggle and `?theme=` query param exist but add nothing to the pitch** — skip
  narrating them; a judge who explores the deployed site after watching will find both.
