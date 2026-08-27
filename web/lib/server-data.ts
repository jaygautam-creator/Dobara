// Server-only data access -- reads the committed evidence/demo JSON synced into web/data/
// (see scripts/sync-data.mjs) via node:fs. Never imported from a "use client" file: the
// point of this module is that demo_batch.json (45.9 MB -- see docs/DECISIONS.md
// [2026-08-26]) never reaches the browser bundle. Pages extract only the trimmed fields a
// client component actually needs before passing them down as props.
import "server-only";
import { readFileSync } from "node:fs";
import path from "node:path";
import type {
  DemoBatchJson,
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
  // Python's json.dump writes bare NaN for float('nan') (e.g. do_nothing's
  // recovery_rate_of_failed_cycles, undefined when n_seeds=0 attempts happened) --
  // valid for Python's own json.load, not standard JSON. JSON.parse rejects it outright,
  // so normalize to null before parsing; every consumer must already handle a missing
  // metric (n_seeds: 0 is the real signal), so null is the correct value here, not 0.
  const normalized = raw.replace(/\bNaN\b/g, "null");
  return JSON.parse(normalized) as T;
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
  return batch.queue.map((item) => ({
    mandate_id: item.mandate_id,
    bank_id: item.bank_id,
    method: item.method,
    merchant_category: item.merchant_category,
    amount: item.amount,
    is_cold_start: item.is_cold_start,
    regime_shift_bank: item.regime_shift_bank,
    action_type: item.decision.chosen.action_type,
    expected_net: item.decision.expected_net,
    confidence_band: item.decision.confidence_band,
    stopping_reason: item.decision.stopping_reason,
    requires_signoff: item.decision.requires_signoff,
    abstain_reason: item.decision.chosen.abstain_reason,
  }));
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
