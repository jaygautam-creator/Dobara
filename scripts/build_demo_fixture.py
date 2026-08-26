"""`make demo-fixture` — builds one live `DemoBatch` against a trained DB
(`data/dobara.sqlite3`) and serialises its API-shaped view to
`artifacts/demo_batch.json`, committed. This is what `api/demo.py::get_demo_data()` loads
when no trained DB is present (a fresh clone, or the static Vercel deploy) — see that
module's docstring for why the fixture path is not a lesser stand-in: it's the same
`agent.decide()` output, computed earlier rather than computed now.

Run after `make train` (needs `data/dobara.sqlite3`). Re-run whenever the demo world seed,
the trained models, or `api/schemas.py`'s response shapes change.
"""

from __future__ import annotations

import json
from pathlib import Path

from api.demo import DEMO_FIXTURE_PATH, demo_data_from_batch, get_demo_batch


def main() -> None:
    batch = get_demo_batch()
    data = demo_data_from_batch(batch, source="fixture")
    payload = {
        "queue": [item.model_dump(mode="json") for item in data.queue],
        "counters": data.counters.model_dump(mode="json"),
        "audit_by_mandate": {
            str(mandate_id): [d.model_dump(mode="json") for d in decisions]
            for mandate_id, decisions in data.audit_by_mandate.items()
        },
        "approvals": [d.model_dump(mode="json") for d in data.approvals],
    }
    DEMO_FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEMO_FIXTURE_PATH.write_text(json.dumps(payload, indent=2))
    size_kb = Path(DEMO_FIXTURE_PATH).stat().st_size / 1024
    print(f"wrote {DEMO_FIXTURE_PATH} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
