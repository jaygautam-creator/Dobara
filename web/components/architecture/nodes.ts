// The system diagram's node registry, docs/10-REDESIGN.md §4 `/architecture`. Every node
// names the file it stands for; `GITHUB_BLOB` turns that into a link, so a judge reading
// the diagram is one click from the code. Descriptions paraphrase docs/02-ARCHITECTURE.md
// "## Module contracts" -- prose only. No number on this page is authored here: the
// compliance-gate panel below the diagram reads artifacts/compliance_rules.json, exported
// from agent/compliance.py itself.

export const GITHUB_BLOB = "https://github.com/jaygautam-creator/Dobara/blob/main";

export type Lane = "money" | "narrative";

export interface DiagramNode {
  id: string;
  label: string;
  sublabel: string;
  lane: Lane;
  /** Repo-relative path this node stands for. */
  file: string;
  description: string;
  /** Layout, in the SVG's own user units (see SystemDiagram's VIEWBOX). */
  x: number;
  y: number;
  w: number;
  h: number;
}

export const NODE_H = 84;

export const NODES: DiagramNode[] = [
  {
    id: "sim",
    label: "Signals",
    sublabel: "outcomes · decline codes · bank health",
    lane: "money",
    file: "sim/engine.py",
    description:
      "What a PSP can actually see: debit outcomes, Razorpay-taxonomy decline codes, timestamps, and per-(bank × method) health. The simulator that generates them holds latent state — each customer's balance-availability process — that the agent is never shown. That asymmetry is what makes the evaluation non-circular: the agent cannot learn its own generator.",
    x: 24,
    y: 36,
    w: 176,
    h: NODE_H,
  },
  {
    id: "features",
    label: "Features",
    sublabel: "strictly pre-decision · Tier 1–3 only",
    lane: "money",
    file: "features/recovery.py",
    description:
      "The leakage boundary. Every feature is computed strictly before the decision timestamp, and a test asserts no feature reads a future row. A second test refuses any feature that would encode an individual's balance or income — rule DPDP-MINIMISE, and CLAUDE.md's 'no individual cash-flow inference' non-negotiable.",
    x: 216,
    y: 36,
    w: 176,
    h: NODE_H,
  },
  {
    id: "models",
    label: "Calibrated models",
    sublabel: "P(success) · P(revoke) · LTV",
    lane: "money",
    file: "models/",
    description:
      "Three tabular, calibrated, inspectable components: a recovery model for P(debit succeeds | context, t), a discrete-time hazard model for P(mandate revoked | attempts, contacts, history), and the LTV estimator that supplies the downside multiplier. No LLM import is permitted in this package, and a test enforces it.",
    x: 408,
    y: 36,
    w: 176,
    h: NODE_H,
  },
  {
    id: "policy",
    label: "Policy",
    sublabel: "argmax E[net], stop at zero",
    lane: "money",
    file: "agent/decide.py",
    description:
      "A pure function: no I/O, no network, no LLM. It prices every legal (action, time) pair, takes the argmax of E[net], stops when the best action is not worth taking, and abstains when the confidence interval on E[net] straddles zero. Because it is pure, every decision on this site is reproducible from its inputs.",
    x: 600,
    y: 36,
    w: 176,
    h: NODE_H,
  },
  {
    id: "gate",
    label: "Compliance gate",
    sublabel: "HARD rules · unrepresentable",
    lane: "money",
    file: "agent/compliance.py",
    description:
      "A declarative rule engine. Each rule carries an id, the regulation it cites, a severity and a source URL. A HARD failure does not warn — it removes the candidate from the set the policy is allowed to choose from, so a non-compliant action cannot be emitted at all. Refusals are logged with the clause that caused them.",
    x: 792,
    y: 36,
    w: 184,
    h: NODE_H,
  },
  {
    id: "action",
    label: "Bounded action set",
    sublabel: "6 actions · closed enum",
    lane: "money",
    file: "agent/actions.py",
    description:
      "Schedule a debit, send the mandated pre-debit notice, offer a permanent date change, escalate to a human, stop, or abstain. A closed enum: there is no seventh thing the agent can express. Actions leave as proposals — Dobara never moves money itself.",
    x: 408,
    y: 168,
    w: 176,
    h: NODE_H,
  },
  {
    id: "audit",
    label: "Audit trail",
    sublabel: "inputs · alternatives · clauses",
    lane: "money",
    file: "agent/audit.py",
    description:
      "Append-only, never mutated. Every decision records what it saw, what the models returned, which action it chose, every alternative it rejected and that alternative's E[net], which compliance clauses were satisfied, and the rupee arithmetic — the six-part SAW / THOUGHT / ALT / GATE / DID / WHY structure the /audit pages render.",
    x: 600,
    y: 168,
    w: 176,
    h: NODE_H,
  },
  {
    id: "harness",
    label: "Batch harness",
    sublabel: "5 arms × 30 seeds · 95% CIs",
    lane: "money",
    file: "eval/run.py",
    description:
      "Runs all five arms over identical held-out populations with identical seeds, and writes artifacts/summary.json. Every number in this UI and in the README is read from those artifacts, never hand-typed — and a make check gate fails the build if an artifact is older than the code that generates it.",
    x: 792,
    y: 168,
    w: 184,
    h: NODE_H,
  },
  {
    id: "llm",
    label: "LLM layer",
    sublabel: "narrative only · disk-cached",
    lane: "narrative",
    file: "llm/provider.py",
    description:
      "Turns a decision that has already been made into English: the root-cause narrative and the audit trail's 'ask why' box. It is given the decision's structured fields and asked to describe them. It is never consulted about what to do, and a grounding gate re-checks every generated sentence's numbers against the decision it describes before the narrative is allowed to ship.",
    x: 408,
    y: 372,
    w: 176,
    h: NODE_H,
  },
  {
    id: "narrative",
    label: "Explanation",
    sublabel: "'ask why' · pre-generated",
    lane: "narrative",
    file: "web/components/AskWhyBox.tsx",
    description:
      "What a human reads. Rendered from a pre-generated cache with the provider and model that wrote each entry shown on the entry itself — so a reader always knows which sentences a language model composed and which came from the decision record.",
    x: 600,
    y: 372,
    w: 176,
    h: NODE_H,
  },
];

/** The test that makes the wall real rather than rhetorical. */
export const BOUNDARY_TEST = "tests/test_no_llm_in_money_path.py";
