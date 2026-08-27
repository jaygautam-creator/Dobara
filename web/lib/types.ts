// Mirrors api/schemas.py's Pydantic response contracts and artifacts/summary.json /
// sensitivity.json's shapes. Kept as a hand-written subset (not generated from the
// OpenAPI schema, since this deploy never calls the live API -- see docs/DECISIONS.md
// [2026-08-26] "Data-shipping architecture") -- just enough of each shape for the pages
// that read it.

export interface Provenance {
  generated_at: string;
  git_commit: string;
}

export interface CIValue {
  // null when genuinely undefined (n_seeds: 0) -- e.g. do_nothing's
  // recovery_rate_of_failed_cycles, undefined because it makes zero attempts, not zero.
  // Never render null as 0; that would misrepresent "no data" as "measured zero".
  point: number | null;
  ci_lo: number | null;
  ci_hi: number | null;
  n_seeds: number;
}

export type ArmName = "do_nothing" | "razorpay_default" | "aggressive_8x" | "dobara" | "oracle";

export interface ArmMetrics {
  gross_recovered_inr: CIValue;
  recovery_rate_of_failed_cycles: CIValue;
  mandate_ever_recovered_rate: CIValue;
  attempts_mean: CIValue;
  attempts_mean_in_failed_cycles: CIValue;
  notifications_total: CIValue;
  revocations_total: CIValue;
  net_ltv_total: CIValue;
  human_escalations_total: CIValue;
  abstentions_total: CIValue;
  recovered_per_notification: CIValue;
}

export interface PairedComparison {
  metric: string;
  arm_a: string;
  arm_b: string;
  mean_diff: number;
  ci_lo: number;
  ci_hi: number;
  significant: boolean;
  n_paired_seeds: number;
}

export interface BankSlice {
  n_mandates: number;
  mandate_recovered_rate: number;
  mean_net_ltv_inr: number;
  revocations: number;
}

export interface PermanentHoldout {
  served_population: { n_mandates: number; mandate_recovered_rate: number; mean_net_ltv_inr: number };
  holdout_control_population: {
    n_mandates: number;
    mandate_recovered_rate: number;
    mean_net_ltv_inr: number;
  };
  note: string;
}

export interface SummaryJson {
  n_seeds: number;
  seeds: number[];
  n_customers_per_seed: number;
  elapsed_seconds: number;
  headline_comparison: string;
  arms: Record<ArmName, ArmMetrics>;
  paired_dobara_vs_razorpay_default: PairedComparison;
  paired_aggressive_8x_vs_razorpay_default: PairedComparison;
  paired_dobara_vs_do_nothing: PairedComparison;
  robustness_slices: {
    note: string;
    by_bank: Record<"dobara" | "razorpay_default", Record<string, BankSlice>>;
    regime_shift_bank_flag: Record<"dobara" | "razorpay_default", Record<"True" | "False", BankSlice>>;
  };
  permanent_holdout_arm: PermanentHoldout;
  credibility_anchor: string;
  provenance: Provenance;
}

export interface SensitivityPoint {
  hazard_per_failure_notification: number;
  dobara_mean_net_ltv: number;
  dobara_ci: [number, number];
  razorpay_default_mean_net_ltv: number;
  razorpay_default_ci: [number, number];
  aggressive_8x_mean_net_ltv: number;
  aggressive_8x_ci: [number, number];
  dobara_minus_razorpay_default: number;
  dobara_wins_vs_razorpay_default: boolean;
  dobara_minus_aggressive_8x: number;
  dobara_beats_aggressive_8x: boolean;
  razorpay_default_revocation_per_execution_ratio: number;
}

export interface OtherAxisPoint {
  value: number;
  dobara_mean_net_ltv: number;
  razorpay_default_mean_net_ltv: number;
  aggressive_8x_mean_net_ltv: number;
  ranking: string[];
}

export interface OtherAxis {
  output_key: string;
  sensitivity_range: [number, number];
  points: OtherAxisPoint[];
  ranking_ever_changes: boolean;
}

export interface SensitivityJson {
  seed: number;
  n_customers: number;
  swept_parameter: string;
  sensitivity_range: [number, number];
  calibrated_value: number;
  points: SensitivityPoint[];
  break_even_vs_aggressive_8x: {
    found: boolean;
    dobara_beats_aggressive_8x_at_every_tested_point?: boolean;
    note: string;
  };
  break_even_vs_razorpay_default: {
    found: boolean;
    hazard_per_failure_notification?: number;
    between_points?: [number, number];
    note: string;
    razorpay_default_revocation_per_execution_ratio_at_break_even?: number;
  };
  other_axes: Record<string, OtherAxis>;
  provenance: Provenance;
}

export interface ReliabilityDiagram {
  prob_true: number[];
  prob_pred: number[];
}

export interface ModelVariant {
  n: number;
  brier_score: { point: number; ci_lo: number; ci_hi: number };
  brier_climatology: number;
  brier_skill_score: number;
  reliability_diagram: ReliabilityDiagram;
  roc_auc: { point: number; ci_lo: number; ci_hi: number };
  pr_auc: { point: number; ci_lo: number; ci_hi: number };
}

export interface RecoveryModelReport {
  model_version: string;
  n_test_evaluations: number;
  n_train: number;
  n_validate: number;
  n_test: number;
  n_cold_start: number;
  lightgbm: { calibrated: ModelVariant; uncalibrated: ModelVariant };
  logistic_baseline: { calibrated: ModelVariant; uncalibrated: ModelVariant };
  beats_baseline: boolean;
  slices: {
    by_bank: Record<string, ModelVariant>;
    by_regime_shift_bank: Record<"True" | "False", ModelVariant>;
  };
}

export interface HazardModelReport {
  model_version: string;
  n_train: number;
  n_validate: number;
  n_test: number;
  n_cold_start: number;
  calibrated: ModelVariant;
  uncalibrated: ModelVariant;
}

export interface MoneyChartSeries {
  gross: number[];
  net: number[];
}

export interface MoneyChartData {
  seed: number;
  n_customers: number;
  cycle_index: number[];
  do_nothing: MoneyChartSeries;
  razorpay_default: MoneyChartSeries;
  aggressive_8x: MoneyChartSeries;
  dobara: MoneyChartSeries;
  oracle: MoneyChartSeries;
}

// --- Control Room / demo_batch.json shapes, mirroring api/schemas.py ---

export interface RupeeMathOut {
  p_success: number;
  amount: number;
  p_revoke: number;
  ltv_remaining: number;
  cost: number;
  expected_net: number;
}

export interface RejectedAlternativeOut {
  description: string;
  expected_net: number;
  reason: string;
}

export interface ClauseRefOut {
  id: string;
  citation: string;
}

export interface ActionOut {
  action_type: "schedule_debit" | "offer_date_change" | "stop" | "abstain" | "escalate_to_human";
  scheduled_at?: string | null;
  channel?: string | null;
  notice_at?: string | null;
  new_preferred_day?: number | null;
  stop_reason?: string | null;
  abstain_reason?: string | null;
  escalate_reason?: string | null;
}

export interface DecisionOut {
  mandate_id: number;
  cycle_index: number;
  attempt_index: number;
  bank_id: string;
  method: string;
  amount: number;
  now: string;
  chosen: ActionOut;
  expected_net: number;
  confidence_band: [number, number];
  rejected_alternatives: RejectedAlternativeOut[];
  clauses_satisfied: ClauseRefOut[];
  clauses_blocked: ClauseRefOut[];
  rupee_math: RupeeMathOut;
  model_versions: Record<string, string>;
  stopping_reason: string | null;
  requires_signoff: boolean;
  audit_text: string;
}

export interface QueueItemOut {
  mandate_id: number;
  bank_id: string;
  method: string;
  merchant_category: string;
  amount: number;
  is_cold_start: boolean;
  regime_shift_bank: boolean;
  decision: DecisionOut;
}

export interface CounterOut {
  n_mandates: number;
  amount_at_risk_inr: number;
  gross_recovered_inr: number;
  net_ltv_inr: number;
  notifications_sent: number;
  revocations: number;
  attempts_not_made: number;
  comparison_aggressive_8x_gross_recovered_inr: number;
  comparison_aggressive_8x_net_ltv_inr: number;
  comparison_aggressive_8x_revocations: number;
}

export interface DemoBatchJson {
  queue: QueueItemOut[];
  counters: CounterOut;
  audit_by_mandate: Record<string, DecisionOut[]>;
  approvals: DecisionOut[];
}

/** Trimmed queue row for the Control Room's list view -- no audit_text/rejected_alternatives,
 * which are only fetched on demand for the case actually opened. */
export interface QueueRow {
  mandate_id: number;
  bank_id: string;
  method: string;
  merchant_category: string;
  amount: number;
  is_cold_start: boolean;
  regime_shift_bank: boolean;
  action_type: ActionOut["action_type"];
  expected_net: number;
  confidence_band: [number, number];
  stopping_reason: string | null;
  requires_signoff: boolean;
  abstain_reason?: string | null;
}
