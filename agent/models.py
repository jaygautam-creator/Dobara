"""`ModelBundle` — loads the persisted Phase 2 artifacts (recovery model, hazard model,
LTV life table, bank-health snapshots, and each model's slice metrics) into the
in-memory bundle `agent/decide.py` scores candidates against.

Building this bundle is the only place in the agent that touches disk or a DB —
`decide()` itself never does (docs/06-AGENT-SPEC.md: "`agent/decide.py` is a **pure
function**: no I/O, no network, no LLM, no clock. Everything it needs arrives in
`DecisionContext`."). `load_model_bundle` is the I/O boundary; everything downstream of
it is plain data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from models.bank_health import load_snapshots
from models.hazard import TrainedHazardModel, load_hazard_model
from models.ltv import LifeTable, build_life_table
from models.recovery import TrainedRecoveryModel, load_recovery_model
from sim.params import Params, load_params


@dataclass(frozen=True)
class ModelBundle:
    recovery: TrainedRecoveryModel
    hazard: TrainedHazardModel
    life_table: LifeTable
    # The full `sim/params.yaml`, not just the `ltv.*` block — `agent/decide.py` also
    # reads `notification.cost_inr.*` from it for the `cost(channel, retry)` term and
    # `afa.threshold_inr*` for the AFA check, rather than duplicating those numbers into
    # `config/policy.yaml` (docs/01-REGULATORY.md's rule table cites the same sourced
    # values either way; one copy is the honest one).
    sim_params: Params
    # Slice metrics as reported at training time (`models/recovery.py`/`models/hazard.py`
    # `_slice_metrics`) — read-only lookup for the abstention checks in `agent/decide.py`,
    # not recomputed here.
    recovery_slices_by_bank: dict[str, Any]
    hazard_slices_by_method: dict[str, Any]
    bank_health: pd.DataFrame

    @property
    def model_versions(self) -> dict[str, str]:
        return {"recovery": self.recovery.model_version, "hazard": self.hazard.model_version}


def load_model_bundle(db_path: str, artifacts_dir: str = "artifacts") -> ModelBundle:
    artifacts = Path(artifacts_dir)
    recovery_report = json.loads((artifacts / "recovery_model_report.json").read_text())
    hazard_report = json.loads((artifacts / "hazard_model_report.json").read_text())

    sim_params = load_params()
    horizon_cycles = int(sim_params.get("ltv.horizon_cycles"))

    return ModelBundle(
        recovery=load_recovery_model(recovery_report["model_version"], str(artifacts / "models")),
        hazard=load_hazard_model(hazard_report["model_version"], str(artifacts / "models")),
        life_table=build_life_table(db_path, horizon_cycles),
        sim_params=sim_params,
        recovery_slices_by_bank=recovery_report["slices"]["by_bank"],
        hazard_slices_by_method=hazard_report["slices"]["by_method"],
        bank_health=load_snapshots(db_path),
    )
