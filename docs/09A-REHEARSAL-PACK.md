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

### Beat 3 — The demonstration (1:05–2:00)

**URL:** same page, scroll to the two-lane demonstration.

**Click:** the demonstration is scroll-triggered and click-to-skip/replay — use the
skip control once to show it's not a forced wait, then let it play once normally, or
replay from the start if you skipped too early.

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
  Across that set: p25 = **₹1,212.39**, p75 = **₹7,006.13**. Say "median case, not the
  best one" and cite the p25–p75 spread — do not round past these figures.

### Beat 4 — Live case, opened (2:00–2:35)

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

### Beat 5 — Graceful failure (2:35–3:05)

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

### Beat 6 — The evidence (3:05–3:50)

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

### Beat 7 — The architecture, and watching it decide (3:50–4:50)

**URL:** `https://dobara-one.vercel.app/architecture`

**Click 1:** click one node in the money lane (e.g. **"Compliance gate"**) to open its
side panel — shows the module description, its source file (`agent/compliance.py`),
and a GitHub link. This is the click that proves the diagram is interactive, not a
static image.

Say: "Money decisions never pass through a language model — that's not a policy, it's a
wall a test enforces; the LLM only narrates, on the other side." Name what was
deliberately not built: no individual cash-flow inference, no probing debits, no LLM
anywhere near the money path.

**Scroll to "Watch it decide"** (added this session — `docs/DECISIONS.md` [2026-08-30]
"Decision walkthrough component"). This is the first place on the site a viewer watches
the agent actually decide, rather than reading about the mechanism in prose.

**Click 2:** let it play once (it self-advances; click anywhere on the card to skip to
the end if you're short on time), on the default **"Stop wins at ₹0"** case.

**What's on screen (verified 2026-08-30 against `artifacts/demo_batch.json` — mandate
13, cycle 4, attempt 3):** the agent priced 76 candidates this cycle (every retry
channel and date, summed from the fixture's own tied-group counts) and every one of
them scored negative — the three shown individually are retries at −₹103.16, −₹103.31,
−₹103.51. `Stop` wins at exactly **₹0.00**, the highest score on the table, because zero
genuinely beats every priced alternative. Say: "This is the thesis on one screen — not
an aggressive agent retrying less, an agent that priced every option and found none of
them worth taking."

**Click 3 (optional, if time allows):** click the **"Abstain, not guess"** tab — mandate
47, cycle 6, attempt 3. Point estimate **+₹28.90**, but its 95% confidence band
(**[−₹10.03, ₹66.83]**) straddles zero, so the agent declines to act on a number it
doesn't trust rather than gamble. Say: "Not every abstention is a bank it's already
learned to distrust — sometimes it's just not confident enough in its own arithmetic to
bet, even when the point estimate is positive."

**Do not state a candidate-generation or gate-filtering count** — the fixture doesn't
record how many candidates the compliance gate struck out before scoring, and the
component correctly doesn't claim one; don't improvise one on camera either.

**Not narrated — for a judge exploring after the video:** further down `/architecture`,
after the compliance-gate sequence, three new sections (`#how-this-is-used`,
`#what-it-refuses`, `#not-built-yet`, added `docs/DECISIONS.md` [2026-08-31] "Adoption
and boundary section on /architecture") answer who touches the system (merchant,
Razorpay, customer), what it structurally refuses to look at, and what is honestly not
built yet (the webhook→decision queue). This does not add screen time to Beat 7 and is
not part of the walkthrough click sequence. If a take runs short and you want one extra
sentence to fill it, an optional line for the compliance-gate moment: "Dobara never
touches the payment rail itself — it proposes, a licensed PA executes, and the customer
never sees Dobara at all."

### Beat 8 — Close (4:50–5:00)

**URL:** `https://dobara-one.vercel.app/` or `/architecture`, hold on the motto.

Say: "The agent's best outcome is making itself unnecessary for that customer. Recover
the payment. Keep the mandate."

## Timing (sums to 5:00)

| Beat | Window | Duration |
|---|---|---|
| 1. Hook + mechanism | 0:00–0:45 | 0:45 |
| 2. Thesis | 0:45–1:05 | 0:20 |
| 3. Demonstration | 1:05–2:00 | 0:55 |
| 4. Live case (Control Room + `/audit/89`) | 2:00–2:35 | 0:35 |
| 5. Graceful failure (`/audit/144`) | 2:35–3:05 | 0:30 |
| 6. Evidence | 3:05–3:50 | 0:45 |
| 7. Architecture + decision walkthrough | 3:50–4:50 | 1:00 |
| 8. Close | 4:50–5:00 | 0:10 |

Thesis lands inside the first 45 seconds (end of Beat 1 / start of Beat 2), per the
requirement.

**This session's timing change, and what it cost.** Adding the decision walkthrough to
Beat 7 doubled it (0:30 → 1:00) — walking situation → candidates → clauses →
arithmetic on camera, even at a skip-ahead pace, doesn't fit in 30 seconds alongside the
existing node-click and "what we didn't build" beats. Rather than let the video run
long, **Beat 4 lost 0:15** (drop the `aggressive_8x` comparison-toggle aside — say the
counter, skip triggering the animated delta) and **Beat 6 lost 0:15** (state the
headline lift and the `aggressive_8x`/`razorpay_default` break-even results; skip
narrating the money chart's cycle-by-cycle crossover detail, since the break-even framing
already carries the same point). Total still sums to 5:00. If Beat 7 still runs long in
a real take, the second click (the abstain case) is marked optional above and is the
first thing to cut — the Stop case alone carries the thesis.

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
```

If any of these disagree with this pack, update the specific figure here (and, if it
also appears in `docs/09-DEMO-SCRIPT.md`, there too) before recording — never narrate a
number this file states without re-checking it against the artifact or the live page.
