# 09A — Rehearsal Pack

> Companion to `docs/09-DEMO-SCRIPT.md`, which stays the structural script (beats,
> timing, what to say in prose). This file exists so recording is a one-take job: exact
> URLs in order, exact figures with their CIs as the live site displays them today, the
> exact case IDs, click targets, and fallbacks. Every number below was read from the
> **live deploy** at `https://dobara-one.vercel.app` (commit `afe326f`, redeployed
> 2026-08-30) or from `artifacts/*.json` directly — **re-read both before recording**,
> since a later `make eval` / `python -m eval.sensitivity` rerun moves them.

## Before you press record

1. Open every URL below once, in order, so build-time data and fonts are warm.
2. Confirm the browser theme is **light** (the site's default as of this session —
   `docs/DECISIONS.md` [2026-08-30]). Do not toggle themes mid-recording.
3. Confirm `/audit/89` cycle 6's second attempt and `/audit/144` cycle 7 still show what
   this pack says (see "Verification" note per beat) — re-run the two `python3` snippets
   in the "How to re-verify" section at the bottom if in doubt.
4. Pre-scroll `/audit/89` to cycle 6's second attempt (the `stop` decision) and
   `/audit/144` to cycle 7, so you land there directly instead of scrolling on camera.

## Shot-by-shot

### Beat 1 — The hook + the mechanism (0:00–0:45)

**URL:** `https://dobara-one.vercel.app/` — hero, then scroll past the new "What this
is" mechanism strip (added this session, task 3) into the three-fact band.

Say: "Twenty million UPI AutoPay mandates are revoked in India every month — not
because customers don't want to pay, but because the debit failed and the merchant kept
retrying. Indian regulation requires every retry on a mandate to carry its own 24-hour
pre-debit notification. No exceptions, no silent retry. So the standard dunning playbook
— retry, retry, retry, up to eight times — is, under Indian law, a mandated stream of
messages telling a customer their merchant keeps failing to take their money."

**Click:** none yet — this beat is scroll-only.

**Numbers, exactly as `/` displays them (three-fact band):**
- **20M+** — "UPI AutoPay mandates are revoked every month in India." Source: *Business
  Standard, 2025* (linked).
- **24h** — "Minimum notice before every debit attempt, retries included." Source: *RBI
  e-mandate framework — docs/01-REGULATORY.md*.
- **8×** — "Retries the standard playbook allows." Source: *docs/01-REGULATORY.md*.

These are counts/thresholds from regulation, not statistical estimates — no CI applies;
say the source aloud for at least one (the 20M figure), per the demo script's rule.

### Beat 2 — The thesis (0:45–1:05)

**URL:** same page, hero — already on screen.

Say the motto verbatim off the page: *"Recover the payment. Keep the mandate."*

### Beat 3 — The demonstration (1:05–1:45)

**URL:** same page, scroll to the two-lane demonstration.

**Click:** the demonstration is scroll-triggered and click-to-skip/replay — use the
skip control to move through it faster than a full real-time playback; this beat is
0:40, trimmed from 0:55 (2026-09-02, to pay for the new calibrator-experiment beat —
see the timing table below), so do not let both lanes play out in full.

**The live case (mandate 4838, seed 301), read from `artifacts/home_demo.json`, verified
against the live page 2026-08-30:**
- Selection: median case by Dobara's net-LTV advantage, among 745 candidates (of 5,000
  mandates) that `aggressive_8x` revoked and `dobara` kept.
- **`aggressive_8x` lane:** 5 notifications sent, 0 successful debits, mandate revoked
  at cycle 1, ₹1,460.93 LTV lost.
- **`dobara` lane:** 8 notifications sent, 6 successful debits, mandate never revoked,
  ₹0 LTV lost. (Dobara sends *more* notifications here, not fewer — say this explicitly;
  the point is "retry exactly as long as the bet is positive," not "always retry less.")
- Net-LTV advantage on this mandate: **₹3,139.76**, the **median** of the 745-case set.
  Across that set: p25 = **₹1,212.39**, p75 = **₹7,006.13**. **In this trimmed 0:40 cut,
  say "median case, not the best one" but skip citing the p25–p75 spread aloud** — it's
  on screen for a viewer who pauses; if recording a longer cut, restore the full line
  from before 2026-09-02 (cite both figures, do not round past them).

### Beat 4 — Live case, opened (1:45–2:20)

**URL 1:** `https://dobara-one.vercel.app/control-room`

**Click:** point at the **"Attempts not made"** counter (the `feature`-treatment tile).
As of the live fixture: **44**. Say: "that's the thesis counter, not a vanity metric —
it's Dobara declining to send a notification it calculated wasn't worth the mandate
risk." Optionally trigger the `aggressive_8x` comparison toggle once to show the
animated deltas — do not narrate the exact delta numbers unless you re-check them live,
since this pack does not pin them.

**URL 2:** `https://dobara-one.vercel.app/audit/89` — scroll to **cycle 6, the second
attempt** (timestamp `2026-06-03T10:00:00`). This is *not* cycle 6's first attempt (an
ordinary `schedule_debit`) — land on the second card within cycle 6.

**What's on screen (verified against `artifacts/demo_batch.json` 2026-08-30):**
- Chosen action: **`stop`** (`stop_reason: negative_expected_value`), expected net ₹0.
- Rejected alternative to name aloud: **"retry via whatsapp"**, scored **−₹715.67**
  (lower by ₹715.67 than the chosen stop). This is the one alternative in this fixture
  with both a concrete single description and a clearly negative expected net — say the
  number, not "negative," so it reads as arithmetic rather than a label.
- Walk the SAW → THOUGHT → ALT → GATE → DID → WHY grid left to right: what the agent
  saw, the calibrated probabilities with CIs, this rejected alternative, the compliance
  clauses lighting green, the worked rupee equation, the `stop` action taken.

### Beat 5 — Graceful failure (2:20–2:50)

**URL:** `https://dobara-one.vercel.app/audit/144` — scroll to **cycle 7** (the first of
two consecutive abstains; cycle 8 also abstains, but land on 7).

**Verified 2026-08-30 against `artifacts/demo_batch.json`:** bank `SBI` (the injected
`regime_shift_bank` case); cycles 1–6 are ordinary `schedule_debit` decisions; cycle 7's
chosen action is **`abstain`**, `abstain_reason: bank_health_changepoint` — **not**
`insufficient_confidence` (the older script text named the wrong reason; corrected this
session). Cycle 8 abstains again for the same reason.

Say: "When the bank-health monitor flags a real shift in this bank's behaviour and the
model can't yet trust its own calibration there, the agent doesn't guess and it doesn't
fall back to an attempt. It stops and says why."

### Beat 6 — The evidence (2:50–3:35)

**URL:** `https://dobara-one.vercel.app/evidence`

**Click:** none required; scroll from the headline `hero` stat through the five-arm
table to the money chart and the break-even section. The page has a sticky left rail
with scroll-spy if you want to jump directly to `#break-even`.

**Numbers, read from the live page 2026-08-30 (headline section):**
- Net LTV lift per mandate: **₹66**, 95% CI **[₹53, ₹80]** — paired vs `razorpay_default`,
  30 seeds, CI excludes zero.
- Net LTV lift, total (one seed): **₹3.29L**, 95% CI **[₹2.67L, ₹4.01L]**.

Say: "Dobara doesn't recover the most gross rupees — the aggressive arm does, for a
while. It recovers the most **net** lifetime value, because it isn't paying for that
gross with mandates it destroys." **If short on time (this beat is now 0:45, trimmed
this session), stop there** — the money-chart cycle-by-cycle detail ("`aggressive_8x`
loses on net LTV from cycle 1, and past cycle 4 loses on gross recovery too") is the
line to cut; the break-even framing below already carries the same point with a number
attached.

**Break-even, read from the live page 2026-08-30 (this replaces the older "no
break-even exists" framing — say it this way, not as a retraction):**
- Against `aggressive_8x`: no break-even found anywhere in the declared range
  [0.05, 0.15] — `dobara` wins at every tested point.
- Against `razorpay_default`: no break-even inside the declared range either, but the
  extended search past it finds one — widening the hazard parameter down toward its
  physical floor (0), break-even is located at **hazard ≈ 0.0371**. The calibrated
  value, **0.098**, sits **2.64×** above it. Anchored against NPCI: at this break-even,
  `razorpay_default`'s own revocation ratio would be **≈1.23%**, against NPCI's
  published **≈2.5%** — real-world revocations would need to run at roughly half the
  published rate for `dobara` to lose.

**Do not state a required minimum gross-margin threshold** — an earlier ≈48% claim was
retracted after a later artifact regeneration and the live page no longer states one.

### Beat 7 — The calibrator experiment (3:35–4:20) — NEW, 2026-09-02

**URL: none new — hold on `https://dobara-one.vercel.app/evidence`, already on screen
from Beat 6.** **This result is not shown anywhere on the deployed site as of this
writing.** There is no dedicated section, chart, or callout for it on `/evidence`,
`/architecture`, or anywhere else in `web/`. This beat is narrated over a held, static
frame — a deliberate placement decision, not an oversight, flagged to the owner rather
than silently worked around. If a section is added to `/evidence` before recording,
update this pack with the real click target; until then, do not invent one.

**Click:** none. Optionally scroll back to the `/evidence` hero as a visual reset before
speaking, but no new content appears.

Say (tightened for delivery, pre-registration clause kept — do not drop it):

> "We pre-registered the rule before measuring. A better-scoring calibrator passed it —
> cut argmax ties from 76% to 18%. We adopted it, reran the full evaluation, and the
> agent got worse on both channels at once: recovered less money, revoked more
> mandates. Both results are published in the repo, in full. We shipped the one that
> wins on net lifetime value, not on the proxy metric."

Optional line if the take is running under 0:45: "Later dates, not fewer attempts, is
where it went wrong — exactly what our own stopping rule was written to prevent."

**Every figure in this beat, with its committed source (verify all before recording —
this experiment lives on `experiment/platt-calibrator`, not `main`; `artifacts/`
references below are on that branch unless noted):**

| Figure spoken | Value | Source (file, on `experiment/platt-calibrator` unless noted) |
|---|---|---|
| "cut argmax ties from 76% to 18%" | 75.7% → 17.9% (all-decisions slice; paired, single measurement) | `artifacts/production_tie_rate.json`, `slices.all_decisions_with_alternatives` |
| "pre-registered the rule before measuring" | adoption rule fixed before the bake-off ran | `docs/DECISIONS.md` [2026-09-01] "Pre-registration: calibrator bake-off" (this entry is on `main` too — written before the bake-off script was ever run) |
| "recovered less money" | −₹376,733 gross, one seed | `docs/DECISIONS.md` [2026-09-02] "Platt adopted" side-by-side table (both branches; figure is identical on `main`'s copy of the same entry) |
| "revoked more mandates" | +78.7/seed (637.7 → 716.4) | same table |
| "we shipped the one that wins on net lifetime value" | +₹65.71/mandate (shipped, `main`) vs. −₹64.09/mandate (Platt, `experiment/platt-calibrator`) | `artifacts/summary.json` on each respective branch; also `README.md`'s "The calibrator experiment" section on `main` |

**If asked in Q&A "why isn't this on the site":** say exactly that — it was a deliberate
scope decision this session, not a technical limitation; the full result is in the
repo's README and `docs/DECISIONS.md`, and the losing branch (`experiment/platt-
calibrator`) stays pushed, permanently, as the record. Do not imply it's shown on
`/evidence` if a judge asks to see it live.

### Beat 8 — The architecture, and watching it decide (4:20–4:50)

**URL:** `https://dobara-one.vercel.app/architecture`

**Click 1:** click one node in the money lane (e.g. **"Compliance gate"**) to open its
side panel — shows the module description, its source file (`agent/compliance.py`),
and a GitHub link. This is the click that proves the diagram is interactive, not a
static image.

Say: "Money decisions never pass through a language model — that's not a policy, it's a
wall a test enforces; the LLM only narrates, on the other side." Name what was
deliberately not built: no individual cash-flow inference, no probing debits, no LLM
anywhere near the money path.

**Scroll to "Watch it decide."** This is the first place on the site a viewer watches
the agent actually decide, rather than reading about the mechanism in prose.

**Click 2:** let it play once, or click anywhere on the card to skip to the end, on the
default **"Stop wins at ₹0"** case. **This beat is 0:30, trimmed from 1:00
(2026-09-02) — run this ONE case only.** The "Abstain, not guess" case (previously
Click 3, mandate 47) is cut entirely from this cut, not merely marked optional; the
Stop case alone carries the thesis.

**What's on screen (verified 2026-08-30 against `artifacts/demo_batch.json` — mandate
13, cycle 4, attempt 3):** the agent priced 76 candidates this cycle and every one of
them scored negative — the three shown individually are retries at −₹103.16, −₹103.31,
−₹103.51. `Stop` wins at exactly **₹0.00**, the highest score on the table. Say: "This
is the thesis on one screen — an agent that priced every option and found none of them
worth taking."

**Do not state a candidate-generation or gate-filtering count** — the fixture doesn't
record how many candidates the compliance gate struck out before scoring; don't
improvise one on camera.

**Not narrated — for a judge exploring after the video:** further down `/architecture`,
after the compliance-gate sequence, three sections (`#how-this-is-used`,
`#what-it-refuses`, `#not-built-yet`) answer who touches the system, what it
structurally refuses to look at, and what is honestly not built yet. Does not add
screen time to Beat 8 and is not part of the walkthrough click sequence.

### Beat 9 — Close (4:50–5:00)

**URL:** `https://dobara-one.vercel.app/` or `/architecture`, hold on the motto.

Say: "The agent's best outcome is making itself unnecessary for that customer. Recover
the payment. Keep the mandate."

## Timing (sums to 5:00)

| Beat | Window | Duration |
|---|---|---|
| 1. Hook + mechanism | 0:00–0:45 | 0:45 |
| 2. Thesis | 0:45–1:05 | 0:20 |
| 3. Demonstration | 1:05–1:45 | 0:40 |
| 4. Live case (Control Room + `/audit/89`) | 1:45–2:20 | 0:35 |
| 5. Graceful failure (`/audit/144`) | 2:20–2:50 | 0:30 |
| 6. Evidence | 2:50–3:35 | 0:45 |
| 7. Calibrator experiment | 3:35–4:20 | 0:45 |
| 8. Architecture + decision walkthrough (one case) | 4:20–4:50 | 0:30 |
| 9. Close | 4:50–5:00 | 0:10 |

Sum check: 45+20+40+35+30+45+45+30+10 = 300 seconds = 5:00. Every window above is
contiguous with the next (no gaps, no overlaps) — verified by construction, each row's
end time equals the next row's start time.

Thesis lands inside the first 45 seconds (end of Beat 1 / start of Beat 2), per the
requirement — unchanged by this session's edits, since only beats 3 and 7–8 moved.

**2026-09-02 timing change, and what it cost.** A new Beat 7 (the calibrator
experiment, `docs/DECISIONS.md` [2026-09-02] "Platt adopted") needed 0:45 and was
placed immediately after Beat 6 (Evidence) — its "strictly dominated, less gross AND
more revocations" punchline only lands once revocations are already established as the
currency Dobara optimizes, which Beat 6 does. Paid for from two places: **Beat 8 (the
architecture + decision-walkthrough beat, formerly Beat 7) lost 0:30** by running the
"Stop wins at ₹0" case only — the "Abstain, not guess" case (previously optional, the
first thing marked for cutting under time pressure even before this change) is now cut
entirely from this timing, not merely marked optional. That covers 0:30 of the new
beat's 0:45; the remaining **0:15 came from Beat 3 (the demonstration), 0:55 → 0:40** —
skip citing the p25/p75 advantage spread aloud in this cut (still on screen). Total
still sums to 5:00, verified above. This supersedes the prior (2026-08-30) timing
change note, which had cut Beats 4 and 6 by 0:15 each (to 0:35/0:45) to make room for
a 1:00 decision-walkthrough window at what was then Beat 7. That trade is undone here:
Beats 4 and 6 keep their 0:35/0:45 durations (they are not cut again), but the
walkthrough itself shrinks to 0:30 (one case, not two) rather than staying at 1:00 —
freeing the 0:30 this change spends on the new Beat 7 instead.

## Fallbacks

- **Live site unreachable / slow build mid-recording:** every route above also exists at
  `localhost:3000` via `make web` (reads the same committed `artifacts/*.json`, since the
  site has no server runtime — `output: "export"`). Record the same shot list against
  localhost and say nothing that claims "live" — the script never uses that word for
  Control Room's replay in particular (see `docs/09-DEMO-SCRIPT.md`'s "What the site
  cannot currently do").
- **A number on screen doesn't match this pack:** trust the screen, not this file — an
  artifact regeneration between this write-up and recording day moves numbers. Re-run the
  verification snippets below and narrate what's actually displayed.
- **Demonstration or Control Room streaming reveal hangs:** click anywhere to skip to the
  end state — this is a documented, built control, not a workaround.

## How to re-verify before recording

```bash
# Confirm /audit/89 cycle 6's second attempt and /audit/144's cycle 7-8 still say what
# this pack claims:
python3 -c "
import json
d = json.load(open('artifacts/demo_batch.json'))
c = [x for x in d['audit_by_mandate']['89'] if x['cycle_index'] == 6 and x['attempt_index'] == 2][0]
print('89/6/2 chosen:', c['chosen']['action_type'], c['chosen']['stop_reason'])
alt = [a for a in c['rejected_alternatives'] if 'whatsapp' in a['description']][0]
print('whatsapp alt expected_net:', alt['expected_net'])
a144 = [x for x in d['audit_by_mandate']['144'] if x['cycle_index'] in (7, 8)]
for x in a144:
    print('144 cycle', x['cycle_index'], x['chosen']['action_type'], x['chosen']['abstain_reason'])
"

# Confirm the home-page demonstration's rupee/notification counts:
python3 -c "
import json
d = json.load(open('artifacts/home_demo.json'))
for arm, lane in d['lanes'].items():
    ev = lane['events']
    notifs = sum(1 for e in ev if e['kind'] == 'attempt')
    succ = sum(1 for e in ev if e.get('outcome') == 'success')
    print(arm, 'notifs', notifs, 'success', succ, 'revoked', any(e.get('revoked') for e in ev))
print('advantage', d['selection']['net_ltv_advantage_inr'])
"

# Confirm the evidence headline and break-even figures:
python3 -c "
import json
s = json.load(open('artifacts/summary.json'))
print(s['paired_dobara_vs_razorpay_default'])
sens = json.load(open('artifacts/sensitivity.json'))
print(list(sens.keys()))
"

# Confirm Beat 7's tie-rate figure. NOTE: this artifact lives on
# experiment/platt-calibrator, not main -- checkout that branch (or fetch the file
# from it) before running this snippet, then return to main before recording.
python3 -c "
import json
d = json.load(open('artifacts/production_tie_rate.json'))
s = d['slices']['all_decisions_with_alternatives']
print('isotonic', s['isotonic']['tie_rate'], 'platt', s['platt']['tie_rate'])
"
```

If any of these disagree with this pack, update the specific figure here (and, if it
also appears in `docs/09-DEMO-SCRIPT.md`, there too) before recording — never narrate a
number this file states without re-checking it against the artifact or the live page.
