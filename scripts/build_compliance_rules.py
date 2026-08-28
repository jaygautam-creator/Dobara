"""`make compliance-rules` -- exports `agent/compliance.py`'s live rule registry to
`artifacts/compliance_rules.json` for `/architecture`'s compliance-gate panel.

The point is that the page cannot drift from the gate it describes. A hand-written copy
of the rule list in the frontend would be a second source of truth that silently goes
stale the first time a rule's text, severity or citation changes -- exactly the failure
mode `docs/DECISIONS.md` [2026-08-27] records for `money_chart_data.json`. This script
reads `RULES` itself, so the only way to change what the page shows is to change the gate.

Cheap and model-free: no trained DB, no simulation. Re-run whenever `agent/compliance.py`
changes; `scripts/check_artifact_freshness.py` enforces it.
"""

from __future__ import annotations

import json
from pathlib import Path

from agent.compliance import RULES
from eval.provenance import stamp

OUT_PATH = Path("artifacts/compliance_rules.json")


def main() -> None:
    payload = {
        "rules": [
            {
                "id": rule.id,
                "text": rule.text,
                "severity": rule.severity.value,
                "citation": rule.citation,
                "source_url": rule.source_url,
            }
            for rule in RULES
        ],
        "n_hard": sum(1 for rule in RULES if rule.severity.value == "hard"),
        "n_soft": sum(1 for rule in RULES if rule.severity.value == "soft"),
        "provenance": stamp(),
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2))
    n_rules = len(RULES)
    print(f"wrote {OUT_PATH} ({n_rules} rules)")


if __name__ == "__main__":
    main()
