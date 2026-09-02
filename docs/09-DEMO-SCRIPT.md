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
| 1:05–1:45 | **The demonstration** | `/` — scroll to the two-lane demonstration (`components/home/Demonstration.tsx`) | Let the aggressive lane fire its notifications on screen into the revocation event and the greyed-out lane, then the Dobara lane — move through this faster than a full real-time playback; skip ahead if the reveal allows it. "Same mandate, same simulated customer, same clock — one policy keeps retrying past the point of no return, the other one doesn't." **Check the actual numbers on screen before speaking them — they are case-specific, not a fixed script.** As of 2026-08-30's `artifacts/home_demo.json` (mandate 4838, seed 301) the shown case is: aggressive fires 5 notifications, gets 0 successful debits, mandate revoked at cycle 1 (₹1,460.93 LTV lost); Dobara fires 8 notifications, gets 6 successful debits, mandate survives (₹0 LTV lost). Dobara sends *more* notifications here, not fewer — say that explicitly. One line on the set this case is drawn from: "median case, not the best one" — do not read the p25/p75 spread aloud in this trimmed cut; it's on screen for anyone who pauses. |
| 1:45–2:20 | **Live case, opened** | `/control-room` briefly (batch counters, "attempts not made" as the `feature` tile), then `/audit/89` scrolled to **cycle 6, second attempt (2026-06-03)** | On Control Room: point at the **attempts not made** counter — "that's the thesis counter, not a vanity metric: it's Dobara declining to send a notification it calculated wasn't worth the mandate risk." Open mandate #89, scroll to cycle 6's *second* attempt — the chosen action there is `stop` (`stop_reason: negative_expected_value`), and the rejected-alternatives list names a concrete losing option, `retry via whatsapp`, scored **−₹715.67** — lower by ₹715.67 than the chosen candidate (0), not a wall of tied candidates. Walk the SAW → THOUGHT → ALT → GATE → DID → WHY grid left to right. **Re-verify the exact rupee figure against the live page before recording** — read from `artifacts/demo_batch.json`'s `audit_by_mandate["89"]`, cycle 6, attempt 2; it moves if the fixture regenerates. |
| 2:20–2:50 | **Graceful failure** | `/audit/144`, scrolled to **cycle 7** | Mandate #144 is bank `SBI` (a `regime_shift_bank` case); cycles 1–6 are ordinary `schedule_debit` decisions, and the agent **abstains at cycle 7 and again at cycle 8** — `abstain_reason: bank_health_changepoint`. Land on cycle 7, the first abstain. "When the bank-health monitor flags a real shift in this bank's behaviour and the model can't yet trust its own calibration there, the agent doesn't guess and it doesn't fall back to an attempt. It stops and says why." |
| 2:50–3:35 | **The evidence** | `/evidence` — headline `hero` stat, the five-arm table, the money chart, the break-even statement | Read the headline stat with its CI. On the five-arm table: "Dobara doesn't recover the most gross rupees — the aggressive arm does, for a while. It recovers the most **net** lifetime value, because it isn't paying for that gross with mandates it destroys." State the break-even result both directions — check `/evidence` at record time, since this moves: as of the current `artifacts/sensitivity.json`, `dobara` beats `aggressive_8x` at every tested hazard point in the declared range — no break-even found there. Against `razorpay_default`, the extended search past the declared range finds one at **hazard ≈ 0.0371**, against a calibrated value of **0.098** — a **2.64×** margin; real-world revocations would need to run at roughly half NPCI's published rate for `dobara` to lose. Do **not** state a required minimum gross-margin figure. |
| 3:35–4:20 | **NEW — The calibrator experiment** | No new URL — **hold on `/evidence`, already on screen from the previous beat.** Nothing on the deployed site currently shows this result; it is narrated over a held, static frame. See `docs/09A-REHEARSAL-PACK.md` Beat 7 for why and what to do about it. | "We pre-registered the rule before measuring. A better-scoring calibrator passed it — cut argmax ties from 76% to 18%. We adopted it, reran the full evaluation, and the agent got worse on both channels at once: recovered less money, revoked more mandates. Both results are published in the repo, in full. We shipped the one that wins on net lifetime value, not on the proxy metric." (Optional, if time allows within 0:45: "Later dates, not fewer attempts, is where it went wrong — exactly what our own stopping rule was written to prevent.") |
| 4:20–4:50 | **The architecture / what we didn't build** | `/architecture` — the LLM-boundary diagram, the compliance gate sequence, then **"Watch it decide," the "Stop wins at ₹0" case only** (the "Abstain, not guess" case is cut entirely from this cut, not merely marked optional) | "Money decisions never pass through a language model — that's not a policy, it's a wall a test enforces." What we deliberately did not build: no individual cash-flow inference, no probing debits, no LLM anywhere near the money path. Let "Stop wins at ₹0" play or skip-to-end once: "This is the thesis on one screen — an agent that priced every option and found none of them worth taking." |
| 4:50–5:00 | **Close** | `/` or `/architecture`, hold on the motto | "The agent's best outcome is making itself unnecessary for that customer. Recover the payment. Keep the mandate." |

Total: 5:00. The demonstration (1:05–1:45) remains the single highest-value asset on
the site per `docs/10-REDESIGN.md` §4. The calibrator-experiment beat (3:35–4:20) was
added 2026-09-02, placed immediately after the evidence beat so its "strictly
dominated" punchline lands once revocations are already established as the currency —
paid for by trimming the demonstration (0:55 → 0:40) and cutting the architecture
beat's decision walkthrough to one case instead of two (1:00 → 0:30). See
`docs/09A-REHEARSAL-PACK.md`'s timing table for the full accounting.

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

- **No on-site section for the calibrator experiment (Beat 7, added 2026-09-02).** The
  deployed site has no chart, callout, or page section for the Platt-calibrator result
  — it is narrated over a held `/evidence` frame with nothing new on screen. Flagged to
  the project owner rather than silently worked around; see
  `docs/09A-REHEARSAL-PACK.md` Beat 7 for the full reasoning and every figure's
  committed source. If `/evidence` gains a section for this before recording, update
  both files with the real click target.
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
