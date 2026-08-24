# 00 — Thesis

## The brief, parsed literally

> **Track 03 — AI Revenue Recovery.** "Find revenue that's slipping away and win it back."
>
> "Build an agent that **detects** revenue at risk, **determines** the right intervention,
> and **executes** a **bounded** recovery workflow: from payment failures and checkout
> abandonment to overdue receivables."
>
> **THE BAR:** "Don't just identify the problem. Show **measured money recovered across a
> batch**, with **compliant escalation**, **stopping rules**, and an **audit trail**."

Word-level reading:

| Word | What it demands |
|---|---|
| detects / determines / executes | Three stages. Most entrants build only stage 1 (a scorer + dashboard). All three are required. |
| **bounded** | Hard limits on autonomous action. |
| "Don't just identify the problem" | An explicit pre-emptive rejection of dashboard-only submissions. |
| **measured money recovered** | Headline metric is ₹, not F1. F1 is supporting evidence. |
| **across a batch** | Not a demo case. An aggregate run harness is a first-class deliverable. |
| **compliant escalation** | Escalation must obey real regulation. India has a specific, citable set. |
| **stopping rules** | When does the agent stop chasing. |
| **audit trail** | Every decision inspectable. |

Three of the four bar requirements are about **restraint**, not capability. The track is
testing whether a builder can touch a customer's money and know when to stop.

---

## The insight

Two facts, both verified, that together define the project.

### Fact 1 — the scale of the leak

> **More than 20 million UPI AutoPay mandates are revoked every month** because the
> customer's account lacked balance at debit time.
> — [Business Standard](https://www.business-standard.com/finance/news/upi-autopay-revocations-hit-20-mn-monthly-over-low-customer-balances-125090700500_1.html)

Against roughly 50 million new mandates registered per month (July 2025, remitter banks,
~2× YoY) and 808 million monthly mandate executions.

The failed debit is not the loss. **It is the trigger.** Debit fails → customer is
notified → customer opens their UPI app and kills the mandate → the merchant loses not
this month's ₹499 but every future ₹499.

### Fact 2 — the mechanism (this is the one nobody else will find)

> **In India a retry requires its own fresh 24-hour pre-debit notification. Retries that
> skip it are rejected outright at the rail — not soft-declined.**
> — [Country-specific retry rules](https://www.slickerhq.com/resources/blog/country-specific-retry-rules-rbi-direct-debit-paypal),
>   [RBI e-mandate framework](https://www.chargebee.com/docs/payments/2.0/others/rbi-e-mandate)

Consequences:

1. **You cannot retry silently in India.** Not "shouldn't" — cannot. Every attempt is
   legally required to be preceded by a message to the customer.
2. **You cannot retry faster than 24 hours.** The reaction loop has a hard floor, so this
   is a *planning* problem, not a reactive one. Greedy retry-when-it-looks-good is
   physically unavailable.
3. **8 retries = 8 mandatory notifications** = eight consecutive messages telling a
   customer this merchant keeps failing to take their money.

The Western dunning playbook — retry aggressively, up to 8 attempts — is, under Indian
regulation, **a legally-mandated harassment machine**. The regulator forced the retry to
be loud and nobody redesigned the strategy around it.

### Therefore

> **Every retry is a bet with downside. Retrying harder can lose more money than not
> retrying at all.**

The link between retrying and revoking is not an assumption in our simulator. It is
structural, forced by regulation, and citable.

---

## What this buys us against the bar

| Bar requirement | Everyone else | Dobara |
|---|---|---|
| stopping rules | "Max 3 attempts." Why 3? Nobody knows. | Derived: stop when `E[recovery] < E[revocation cost]`. A rupee behind the rule. |
| measured money recovered | Gross recovery, one number, one seed. | Net lifetime value, 5 arms, 95% CI over 30 seeds, sensitivity analysis. |
| compliant escalation | A README paragraph saying "we are compliant". | A declarative rule engine; each rule carries its citation; each audit line names the clause it satisfied. |
| audit trail | A log file. | Inputs, model outputs, chosen action, **rejected alternatives and why**, clauses satisfied, rupee maths — per decision. |

**The money chart:** the naive aggressive-retry arm beats us on gross recovery this month
and loses on net lifetime value over the horizon. That crossover is the single best
twenty seconds of the pitch video.

---

## Positioning relative to Razorpay

Three findings that let us stand *inside* their world rather than beside it.

**1. Razorpay's ML team has published.** *An AI-powered Smart Routing Solution for Payment
Systems*, Bygari et al., **IEEE Big Data 2021** ([arXiv 2111.00783](https://arxiv.org/abs/2111.00783)).
Architecture: a **static module** (rule-based filtering + logistic regression predicting
gateway downtime) and a **dynamic module** (success-rate features updated in real time by
an **adaptive time-decay algorithm**, feeding a random forest). Tree-based, not deep
learning. Reported lift: **4–6%**.

- **Build in their idiom.** Static/dynamic split, adaptive time decay on bank-health
  features, tree ensembles. An engineer reads our architecture and recognises the house style.
- **Calibrate our claims to their honesty.** They shipped to production across millions of
  transactions and reported 4–6%. A modest, tightly-confidence-intervalled lift is far more
  credible than a large one. **If our headline number looks too good, we have a bug.**
- **The gap:** they published on routing — *which* terminal. Nobody has published on
  timing — *when* to retry.

**2. Their retry defaults are documented, so the baseline is real.** Retry the following
day; e-mandate retries only after the previous attempt confirms (can exceed 24h);
bank-holiday shift to T-1, or T-3 if two holidays; `pending` → `halted`
([docs](https://razorpay.com/docs/payments/subscriptions/payment-retries/)). Our baseline
arm is *their published production behaviour*, cited — not a strawman.

**3. Their shipped product leaves exactly our question open.** Intelligent Revenue-Protect
(beta, FTX 2026) gives merchants an **Intelligent Retry Engine** where they *configure* a
retry cadence from templates. It is configuration. **Dobara answers the question that
configuration screen asks and cannot answer.**

---

## The creepiness problem, and its answer

Timing a debit to when money is present could feel like surveillance. Three responses.

**We have no balance API.** Razorpay is not the customer's bank. There is no legitimate
way to read an account balance and no illegitimate one we would touch. The surveillance
being imagined is not technically available to us.

**Evidence ladder** (full detail in `docs/01-REGULATORY.md`): Tier 1 declared → Tier 2 our
own interaction history → Tier 3 cohort priors → **Tier 4 individual cash-flow inference,
which we publicly refuse.** Also refused: **probing debits** (a ₹1 test debit to detect
funds — technically clever, ethically indefensible, likely breaches mandate amount terms).

**The mandated notification becomes the consent surface.** RBI already forces a 24-hour
pre-debit notification carrying an opt-out. Today it is a dead formality. We make it live:

> *"₹499 for [merchant] is scheduled tomorrow, the 28th. Tap to move it to the 2nd instead."*

Not surveillance — the customer told us. Not unpredictable — *more* predictable, because
they chose. Zero new intrusion — it is a message the regulator already compels. And it is
the highest-quality training signal available: declared preference beats inferred.

**And we converge, not oscillate.** We do not re-guess the date monthly — that *would*
feel like tracking. We ask once, converge to a stable customer-chosen date, and stop
moving. **The agent's best outcome is making itself unnecessary for that customer.**

Honest caveat for the README: response rates to such prompts are low, single-digit percent.
Tier 1 is a **bonus tier, not a dependency**. The system is complete on Tiers 2–3 alone.

**Interests are aligned, not adversarial.** NACH-based SIP failures carry bounce charges of
₹250–₹750 + GST each, up to ~₹2,950/month for someone running several SIPs
([Business Today](https://www.businesstoday.in/mutual-funds/story/sip-failures-on-nach-mandate-can-cost-you-up-to-rs-2950-per-month-heres-how-524935-2026-04-09)).
UPI AutoPay is gentler — reportedly no penalty except loan/EMI mandates — so state this
precisely rather than claiming it across the board. Where it applies:

> **We are not trying to catch you *with* money. We are trying not to catch you *without* it.**

---

## Where the LLM earns its place — and where it is banned

Stating the boundary is itself a differentiator. "AI Builder" does not mean "wrap
everything in an LLM," and showing you know the difference is a hiring signal.

**Yes:** root-cause narrative for the merchant; composing the customer nudge in the right
language and register (**Hinglish** — one of their listed example directions) *inside* an
approved compliance template; answering "why did the agent do this?" over the audit log.

**Absolutely not:** recovery probability, revocation hazard, timing choice. Tabular,
gradient-boosted, calibrated, inspectable. Money decisions do not pass through a token
sampler. Enforced by module boundary, not by prompt.
