"""`make demo-fixture` — builds one live `DemoBatch` against a trained DB
(`data/dobara.sqlite3`) and serialises its API-shaped view to
`artifacts/demo_batch.json`, committed. This is what `api/demo.py::get_demo_data()` loads
when no trained DB is present (a fresh clone, or the static Vercel deploy) — see that
module's docstring for why the fixture path is not a lesser stand-in: it's the same
`agent.decide()` output, computed earlier rather than computed now.

Run after `make train` (needs `data/dobara.sqlite3`). Re-run whenever the demo world seed,
the trained models, or `api/schemas.py`'s response shapes change.

**Never writes `audit_text`.** It's an 11.7 KB rendered string per decision, fully
derivable from the rest of `DecisionOut`'s already-committed structured fields
(`agent/audit.py::render_fields` / `api/converters.py::render_from_decision_out`) — see
`docs/DECISIONS.md` [2026-08-27]. `api/demo.py`'s fixture loader regenerates it at read
time instead. Ties in `rejected_alternatives` are also already collapsed upstream, in
`agent/decide.py::_rejected_alternatives` — nothing extra to do here for that.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from api.demo import DEMO_FIXTURE_PATH, demo_data_from_batch, get_demo_batch
from api.schemas import DecisionOut, QueueItemOut
from eval.provenance import stamp


def _decision_json(d: DecisionOut) -> dict[str, Any]:
    return d.model_dump(mode="json", exclude={"audit_text"})


def _queue_item_json(item: QueueItemOut) -> dict[str, Any]:
    return item.model_dump(mode="json", exclude={"decision": {"audit_text"}})


def main() -> None:
    batch = get_demo_batch()
    data = demo_data_from_batch(batch, source="fixture")
    payload = {
        "queue": [_queue_item_json(item) for item in data.queue],
        "counters": data.counters.model_dump(mode="json"),
        "audit_by_mandate": {
            str(mandate_id): [_decision_json(d) for d in decisions]
            for mandate_id, decisions in data.audit_by_mandate.items()
        },
        "approvals": [_decision_json(d) for d in data.approvals],
        "provenance": stamp(),
    }
    DEMO_FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEMO_FIXTURE_PATH.write_text(json.dumps(payload, indent=2))
    size_kb = Path(DEMO_FIXTURE_PATH).stat().st_size / 1024
    print(f"wrote {DEMO_FIXTURE_PATH} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
