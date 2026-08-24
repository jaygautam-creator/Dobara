# Copy-paste this at the start of every new build session

Paste the block below verbatim. It works for Sonnet 5 and needs no other context.

---

```
Read CLAUDE.md, then PROGRESS.md, then the docs/ spec named as next in PROGRESS.md.
Then continue the build from the "Next action" line in PROGRESS.md.

Project: Dobara — AI revenue-recovery agent for Indian recurring payments.
Razorpay AI Buildathon, Track 03. Solo. Ship 3 Sep, hard deadline 5 Sep.

Thesis: in India every payment retry legally requires its own 24-hour pre-debit
notification, so aggressive retrying is a mandated harassment machine that destroys
20 million UPI AutoPay mandates a month. Dobara prices each retry as a bet against
mandate revocation and knows when to stop. Motto: "Recover the payment. Keep the mandate."

Rules:
- Follow the specs in docs/. Do not redesign. Do not re-litigate anything in
  docs/DECISIONS.md or docs/03-TECH-STACK.md — if you think one is wrong, say so in one
  paragraph and then follow it anyway.
- Non-negotiables are listed in CLAUDE.md. The important ones: no LLM on the money path,
  no individual cash-flow inference, no probing debits, every reported number carries a
  confidence interval, every simulator parameter carries a source, the compliance gate is
  structural rather than advisory, and the audit trail records rejected alternatives.
- Work in small commits with conventional messages. Run `make check` before finishing.
- Load the `dataviz` skill before writing any chart code.

Finish the session by:
1. Ticking the boxes you completed in PROGRESS.md
2. Rewriting the "## CURRENT STATE" block at the top of PROGRESS.md
3. Appending one line to the session log at the bottom of PROGRESS.md
4. Appending any non-obvious decision to docs/DECISIONS.md
5. Committing and pushing

Do not stop to ask whether to proceed. Work through the phase. Ask only if genuinely
blocked on something the user must supply (an API key, an account, a real-world decision).
```

---

## Notes for the user

- **You do not need to explain anything else.** Everything the model needs is in the repo.
- If a session ends mid-phase that is fine — `PROGRESS.md` carries the state.
- If a session goes off the rails, the recovery prompt is:
  `Re-read CLAUDE.md and PROGRESS.md. Ignore everything else in this conversation. Resume from "Next action".`
- **Day 6 (30 Aug) is the gate.** If `artifacts/summary.json` does not exist by then, paste:
  `The Day 6 gate in PLAN.md was missed. Execute the scope cut: drop the frontend entirely and ship CLI + notebook + README. Update PROGRESS.md accordingly.`
- Escalate back to Opus for: a change to the thesis, the objective function, the evaluation
  design, or anything in `docs/DECISIONS.md`. Sonnet is for execution against these specs.
