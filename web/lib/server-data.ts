// Server-only data access -- reads the committed evidence/demo JSON synced into web/data/
// (see scripts/sync-data.mjs) via node:fs. Never imported from a "use client" file: the
// point of this module is that demo_batch.json (45.9 MB -- see docs/DECISIONS.md
// [2026-08-26]) never reaches the browser bundle. Pages extract only the trimmed fields a
// client component actually needs before passing them down as props.
import "server-only";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import type {
  AskWhyCache,
  AskWhyEntry,
  CalibratorExperimentSummary,
  ComplianceRulesJson,
  DecisionOut,
  DemoBatchJson,
  HomeDemoJson,
  HazardModelReport,
  MoneyChartData,
  QueueRow,
  RecoveryModelReport,
  SensitivityJson,
  SummaryJson,
} from "./types";

const DATA_DIR = path.join(process.cwd(), "data");

function readJson<T>(name: string): T {
  const raw = readFileSync(path.join(DATA_DIR, name), "utf-8");
  // artifacts/summary.json used to contain bare NaN tokens (invalid JSON) -- fixed at
  // the producer (eval/run.py::_json_safe, NaN -> null before json.dumps(allow_nan=False))
  // per docs/DECISIONS.md [2026-08-27], not tolerated here. A NaN reaching this parse
  // now is a real regression in the producer, not something to work around again.
  return JSON.parse(raw) as T;
}

export function getSummary(): SummaryJson {
  return readJson<SummaryJson>("summary.json");
}

export function getSensitivity(): SensitivityJson {
  return readJson<SensitivityJson>("sensitivity.json");
}

export function getRecoveryModelReport(): RecoveryModelReport {
  return readJson<RecoveryModelReport>("recovery_model_report.json");
}

export function getHazardModelReport(): HazardModelReport {
  return readJson<HazardModelReport>("hazard_model_report.json");
}

export function getMoneyChartData(): MoneyChartData {
  return readJson<MoneyChartData>("money_chart_data.json");
}

export function getHomeDemo(): HomeDemoJson {
  return readJson<HomeDemoJson>("home_demo.json");
}

export function getCalibratorExperimentSummary(): CalibratorExperimentSummary {
  return readJson<CalibratorExperimentSummary>("calibrator_experiment_summary.json");
}

export function getComplianceRules(): ComplianceRulesJson {
  return readJson<ComplianceRulesJson>("compliance_rules.json");
}

let _demoBatch: DemoBatchJson | null = null;
function getDemoBatch(): DemoBatchJson {
  if (_demoBatch) return _demoBatch;
  _demoBatch = readJson<DemoBatchJson>("demo_batch.json");
  return _demoBatch;
}

/** The Control Room's list view -- one small row per mandate, ranked by amount.
 * Deliberately excludes audit_text/rejected_alternatives/clauses (the bulk of
 * demo_batch.json's size); those load only when a specific case is opened via
 * getMandateAudit(). */
export function getQueueRows(): QueueRow[] {
  const batch = getDemoBatch();
  return batch.queue.map((item) => {
    const trail = batch.audit_by_mandate[String(item.mandate_id)];
    const terminal = trail && trail.length > 0 ? trail[trail.length - 1] : item.decision;
    return {
      mandate_id: item.mandate_id,
      bank_id: item.bank_id,
      method: item.method,
      merchant_category: item.merchant_category,
      amount: item.amount,
      is_cold_start: item.is_cold_start,
      regime_shift_bank: item.regime_shift_bank,
      action_type: item.decision.chosen.action_type,
      terminal_action_type: terminal.chosen.action_type,
      expected_net: item.decision.expected_net,
      confidence_band: item.decision.confidence_band,
      stopping_reason: item.decision.stopping_reason,
      requires_signoff: item.decision.requires_signoff,
      abstain_reason: item.decision.chosen.abstain_reason,
    };
  });
}

export function getCounters() {
  return getDemoBatch().counters;
}

export function getApprovals() {
  return getDemoBatch().approvals;
}

export function getAllMandateIds(): number[] {
  return Object.keys(getDemoBatch().audit_by_mandate).map(Number);
}

/** Every decision made for one mandate, in order -- the full audit trail, including
 * audit_text. Only called for the one mandate a page/detail view is actually rendering. */
export function getMandateAudit(mandateId: number) {
  const batch = getDemoBatch();
  return batch.audit_by_mandate[String(mandateId)] ?? null;
}

export function getQueueItemSummaryByMandate(mandateId: number) {
  const batch = getDemoBatch();
  return batch.queue.find((q) => q.mandate_id === mandateId) ?? null;
}

/** The full first (highest-₹-at-risk) queue item, decision included -- the Control
 * Room's default "active case" panel, per docs/08-FRONTEND-SPEC.md. Every other row
 * links out to its own statically generated /audit/[id] page rather than shipping every
 * mandate's full decision to the client. */
export function getTopCaseFull() {
  const batch = getDemoBatch();
  return batch.queue[0] ?? null;
}

/** The two decisions `/architecture`'s interactive walkthrough features -- picked by
 * hand (docs/DECISIONS.md [2026-08-30] "Decision walkthrough component"), not generated,
 * because the fixture doesn't record a queryable "most alternatives" index. Both are
 * read from the same committed `demo_batch.json` every other page reads; nothing here is
 * a separate artifact or a re-derivation. Throws at build time (not silently falls back)
 * if either ever goes missing from a regenerated fixture, since a broken pointer here
 * would otherwise ship as a blank interactive component. */
export function getFeaturedDecisions(): { stop: DecisionOut; abstain: DecisionOut } {
  const findCase = (mandateId: number, cycleIndex: number, attemptIndex: number): DecisionOut => {
    const trail = getMandateAudit(mandateId);
    const rec = trail?.find(
      (d) => d.cycle_index === cycleIndex && d.attempt_index === attemptIndex,
    );
    if (!rec) {
      throw new Error(
        `getFeaturedDecisions: mandate ${mandateId} cycle ${cycleIndex} attempt ${attemptIndex} not found in demo_batch.json`,
      );
    }
    return rec;
  };
  return {
    // Stop winning at exactly ₹0.00 against 7 priced, negative alternatives -- the
    // strongest single case in the fixture (verified 2026-08-30: 39 decisions share
    // stop_reason negative_expected_value and expected_net 0.0; this one has the most
    // rejected alternatives of any of them).
    stop: findCase(13, 4, 3),
    // A positive point estimate (+Rs.28.90) whose 95% confidence band straddles zero
    // ([-10.03, 66.83]) -- the agent declines to act on a number it doesn't trust, not
    // just a regime-shift bank it already distrusts (that case is /audit/144).
    abstain: findCase(47, 6, 3),
  };
}

let _askWhyCache: AskWhyCache | null | undefined = undefined;

/** `make ask-why` is a separate, optional, rate-limited step (see
 * scripts/generate_ask_why.py) -- a fresh clone or a build that skipped it has no
 * cache file at all, and even a completed run only covers whatever finished before the
 * script exited. Returns null in both cases so AskWhyBox can render an honest empty
 * state instead of the page failing to build. */
function getAskWhyCache(): AskWhyCache | null {
  if (_askWhyCache !== undefined) return _askWhyCache;
  const p = path.join(DATA_DIR, "llm_cache", "ask_why.json");
  _askWhyCache = existsSync(p) ? (JSON.parse(readFileSync(p, "utf-8")) as AskWhyCache) : null;
  return _askWhyCache;
}

/** Looks up the pre-generated "ask why" entry (narrative text plus which provider/model
 * generated it) for one decision, keyed exactly as
 * scripts/generate_ask_why.py::decision_key() writes it. Returns null when the cache is
 * absent or doesn't (yet) have this decision. */
export function getAskWhy(
  mandateId: number,
  cycleIndex: number,
  attemptIndex: number,
): AskWhyEntry | null {
  const cache = getAskWhyCache();
  if (!cache) return null;
  return cache.narratives[`${mandateId}:${cycleIndex}:${attemptIndex}`] ?? null;
}
