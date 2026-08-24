# 01 — Regulatory & Legal Clearance

**Question asked:** is there any Indian rule that makes this project not allowed?

**Answer: no. Nothing here is prohibited.** Dobara is a decision-support and
workflow-orchestration layer. It handles no funds, holds no licence-triggering role,
stores no card data, and in this build touches only synthetic data and Razorpay **test
mode**. Everything below is the reasoning, plus the rules we convert into executable
constraints — because turning regulation into code is the differentiator, not a chore.

> **Not legal advice.** This is engineering research from public sources, and the README
> must say so. Where a rule is genuinely ambiguous we take the stricter reading and flag it.

---

## 1. Do we need an RBI licence?

**No.** RBI's *Guidelines on Regulation of Payment Aggregators and Payment Gateways*
(17 Mar 2020, effective 1 Apr 2020) apply **mandatorily to Payment Aggregators** — entities
that *handle funds*. Technology-related recommendations apply **voluntarily to Payment
Gateways** (technology providers that do not handle funds).
[Trilegal summary](https://trilegal.com/knowledge_repository/rbis-guidelines-on-regulation-of-payment-aggregators-and-payment-gateways/)

Dobara never receives, holds, pools, or settles money. It emits a *recommendation* —
"attempt this debit at this time" or "stop" — which a licensed PA (Razorpay) executes.
That is a technology service provider role. No authorisation is triggered.

**Design rule this creates:** Dobara must never be architected to move money itself. It
proposes; the PA disposes. Encoded as `AgentAction` objects that are *requests*, never
direct rail calls.

## 2. Data localisation

RBI's *Storage of Payment System Data* directive (6 Apr 2018) requires the **entire
payment data** of authorised Payment System Operators to be stored **only in India**.
[SISA](https://www.sisainfosec.com/blogs/norm-on-storage-of-payment-system-data-by-rbi/) ·
[Appknox](https://www.appknox.com/blog/data-localization-rule-by-rbi)

**Does it bite us?** Not in this build — we process synthetic data and Razorpay test-mode
objects, which are not real payment system data. But we do three things anyway:

- Deploy the app to **Vercel `bom1` (Mumbai)**, so the residency posture is correct by default.
- Document the production path: in a real deployment inside Razorpay, all inference and
  audit storage sits in-region; models are trained on in-region data.
- Note honestly in the README that our managed Postgres free tier has no Mumbai region
  (nearest: Singapore) and that this would be replaced in production.

Showing you know the rule and priced it into the deployment is worth more than the rule
not applying.

## 3. DPDP Act 2023 (India's data protection law)

Consent must be free, specific, informed, unconditional and unambiguous, per purpose.
**Purpose limitation** — data used only for the stated purpose, erased when fulfilled or on
withdrawal. **Data minimisation** (s.6) — collect only what is necessary.
[EY guide](https://www.ey.com/en_in/insights/cybersecurity/decoding-the-digital-personal-data-protection-act-2023)

Our design is *already* the compliant one, which is a happy accident of the ethics:

- Tier-4 individual cash-flow inference is refused → **data minimisation by construction**.
- We use only our own transaction outcomes and aggregate cohort priors → no secondary use.
- The pre-debit notification carries a real choice → consent is affirmative, not assumed.
- Notably, DPDP 2023 (unlike GDPR) has **no right to object to automated decision-making**.
  We give the customer a defer/opt-out control anyway. **Doing more than the law requires,
  and saying so, is the point.**

## 4. Contact conduct — the harassment rules

RBI's Fair Practices Code and the Digital Lending Guidelines (2024–25) bind lenders, NBFCs
and third-party recovery agencies:

- Contact **only between 08:00 and 19:00 IST**. Calls, SMS, WhatsApp and visits outside
  that window are classified as harassment.
- No abusive language, threats or coercion. Female borrowers get added protections.
- Digital lenders are explicitly banned from accessing the borrower's contact list, photos
  or location, and from sending shaming messages to contacts.
- Every recovery interaction must be digitally recorded.

[Bajaj Finserv](https://www.bajajfinserv.in/rbi-guidelines-for-recovery-agents) ·
[Airtel guide](https://www.airtel.in/blog/personal-loan/handle-loan-recovery-agents-rbi-rights-guide/)

**Scope note, stated honestly in the repo:** these bind *lending* recovery. A subscription
merchant collecting a failed OTT debit is not a loan recovery agent. **We adopt them
anyway as hard constraints**, because they encode the regulator's settled view of what
respectful collection looks like, and because "we held ourselves to the stricter standard"
is exactly the sentence you want in a panel interview.

## 5. RBI FREE-AI — the framework to align with by name

On **13 Aug 2025** RBI released the committee report *Framework for Responsible and Ethical
Enablement of Artificial Intelligence* (FREE-AI), chaired by **Dr Pushpak Bhattacharyya**
(IIT Bombay): six pillars, seven guiding principles, twenty-six recommendations.
[RBI PDF](https://rbidocs.rbi.org.in/rdocs/PublicationReport/Pdfs/FREEAIR130820250A24FF2D4578453F824C72ED9F5D5851.PDF) ·
[KPMG](https://kpmg.com/in/en/insights/2025/09/rbis-free-ai-committee-report-in-the-financial-sector.html)

The seven **Sutras**: *safety, transparency, accountability, fairness, inclusivity,
sustainability, explainability.*

**This is the highest-leverage citation in the whole project.** We map every architectural
decision to a named Sutra in the README:

| Sutra | How Dobara satisfies it |
|---|---|
| Safety | Bounded action set; agent proposes, PA executes; hard stop when `E[net] ≤ 0` |
| Transparency | Full audit trail incl. rejected alternatives; simulator params carry sources |
| Accountability | Human sign-off above threshold; named stopping reasons; permanent holdout arm |
| Fairness | No individual cash-flow inference; cohort priors only; no protected-attribute features |
| Inclusivity | Multilingual/Hinglish nudges; customer-chosen debit dates |
| Sustainability | Fewer, better-placed attempts; explicit cost per notification |
| Explainability | Calibrated tabular models, not black-box; per-decision rupee maths in plain language |

> **BUILD TASK:** download the RBI PDF and verify the six pillars verbatim before quoting
> them. Only the seven Sutras are verified as of writing. Do not invent pillar names.

## 6. Verdict

| Concern | Status |
|---|---|
| Licence required | **No** — technology layer, no funds handled |
| Data localisation | **N/A here** (synthetic + test mode); addressed anyway via `bom1` |
| DPDP consent/minimisation | **Compliant by design**; we exceed the requirement |
| Contact conduct rules | **Adopted voluntarily** as hard constraints |
| RBI FREE-AI | **Aligned and mapped**, Sutra by Sutra |
| Offence-capable? | **No.** The system's distinctive behaviour is *restraint*. It exists to attempt fewer, better-timed debits. |

There is no exit. The project is clean, and the compliance work is a feature.

---

## The rules, as executable constraints

Everything below is implemented in `agent/compliance.py` as declarative rules. Each rule
object carries `id`, `rule`, `citation`, `severity`, `source_url`. **An action that fails
any HARD rule cannot be emitted** — the gate returns a refusal, and the refusal itself is
logged with the clause that blocked it.

| ID | Rule | Severity | Basis |
|---|---|---|---|
| `RBI-PDN-24H` | Every debit attempt, **including every retry**, must be preceded by a pre-debit notification ≥24h earlier | HARD | RBI e-mandate framework |
| `RBI-PDN-OPTOUT` | The pre-debit notification must carry an opt-out for this debit and for the mandate | HARD | RBI e-mandate framework |
| `RBI-POST-CONF` | Every successful debit must be followed by a confirmation to the customer | HARD | RBI e-mandate framework |
| `RBI-AFA-15K` | Debits above ₹15,000 require Additional Factor Authentication (₹1,00,000 for insurance / mutual funds / credit-card bills) | HARD | RBI e-mandate framework |
| `RBI-NO-CHARGE` | No charge may be levied on the customer for the e-mandate facility | HARD | RBI e-mandate framework |
| `CONDUCT-HOURS` | No customer contact outside 08:00–19:00 IST | HARD | RBI Fair Practices / Digital Lending |
| `CONDUCT-NO-SHAME` | No contact with third parties; no shaming; no coercive language | HARD | RBI Digital Lending Guidelines |
| `CONDUCT-RECORD` | Every interaction digitally recorded | HARD | RBI Fair Practices |
| `TRAI-DLT` | Commercial SMS only via a registered DLT template; content must match the approved template | HARD | TRAI TCCCPR |
| `WA-UTILITY` | WhatsApp messages must use an approved utility template within the allowed window | HARD | WhatsApp Business Policy |
| `DPDP-PURPOSE` | Data used only for recovery of the mandate it was collected for | HARD | DPDP Act 2023 |
| `DPDP-MINIMISE` | No feature may encode individual balance or cash-flow inference | HARD | DPDP Act 2023 s.6 |
| `DOBARA-NO-PROBE` | No probing/test debits of an amount other than the scheduled one | HARD | Self-imposed |
| `DOBARA-CONVERGE` | A mandate's debit date may be changed at most once per N cycles, and only toward a customer-declared or evidenced-stable date | SOFT | Self-imposed |
| `DOBARA-FATIGUE` | Maximum notifications per mandate per cycle; hard cap regardless of expected value | HARD | Self-imposed |

### The grey area we flag rather than exploit

Sources agree a retry requires its own pre-debit notification, and that retries skipping it
are **rejected outright rather than soft-declined**. What is *not* crisply settled in public
documentation is the precise treatment of a retry occurring inside the original mandate's
cycle. **We take the conservative reading — every attempt gets its own notification —
expose it as `config.retry_requires_fresh_pdn` (default `true`), and flag the ambiguity
openly in the README.**

Finding a grey area, choosing the stricter side, and documenting it is exactly the instinct
a payments company wants in someone touching their money.

## The evidence ladder

| Tier | Source | Used? | Why |
|---|---|---|---|
| 1 | **Declared** — customer chose the date via the pre-debit notification | ✅ | Zero creep, highest quality, consent-based |
| 2 | **Our own interaction history** — outcomes of *our* past debits on *this* mandate | ✅ | Remembering our own transactions, not tracking a person |
| 3 | **Cohort priors** — bank × method × day-of-month failure rates, population salary-cycle effects | ✅ | Aggregate, no individual inference |
| 4 | **Individual cash-flow inference** — modelling this human's balance/income | ❌ **REFUSED** | Surveillance. Documented in README under "What Dobara deliberately does not do" |

Also refused, and named in the README because a clever engineer *would* think of it:
**probing debits** — a ₹1 test debit to detect whether funds exist. Technically elegant,
ethically indefensible, and almost certainly a breach of the mandate's amount terms.

> Declining a capability you obviously could have built, in writing, is worth more in a
> panel interview than any feature.
