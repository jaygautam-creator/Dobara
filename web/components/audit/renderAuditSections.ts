import type { DecisionOut } from "@/lib/types";
import { formatInrPrecise } from "@/lib/format";

/** Rebuilds the SAW/DID/WHY narrative lines directly from `DecisionOut`'s structured
 * fields, mirroring `agent/audit.py::render_fields`/`_did_line`/`_why_line` term for
 * term. The committed `demo_batch.json` never actually serialized an `audit_text`
 * field (despite the type predating this session claiming one) -- every context field
 * `render_fields` prints (`prev_error_*`, `notifications_sent_this_cycle`,
 * `consecutive_failed_cycles`) IS present on the record, so this reconstructs the exact
 * same narrative from the same source data rather than inventing anything new. */

function orNone(v: string | null): string {
  return v ?? "None";
}

export function sawText(d: DecisionOut): string {
  const dayOfMonth = new Date(d.now).getDate();
  return [
    `${d.method} - ${d.bank_id} - ${formatInrPrecise(d.amount)} - prev: ${orNone(d.prev_error_source)}/${orNone(d.prev_error_step)}/${orNone(d.prev_error_reason)}`,
    `day_of_month ${dayOfMonth} - attempt_index ${d.attempt_index}`,
    `notifications_this_cycle ${d.notifications_sent_this_cycle} - consecutive_failed_cycles ${d.consecutive_failed_cycles} - mandate_age ${d.cycle_index - 1}`,
  ].join("\n");
}

export function didText(d: DecisionOut): string {
  const a = d.chosen;
  switch (a.action_type) {
    case "schedule_debit":
      return `SEND_PRE_DEBIT_NOTICE(${a.notice_at}, ${a.channel})\nSCHEDULE_DEBIT(${a.scheduled_at})   [proposal -> rzp test mode]`;
    case "offer_date_change":
      return `OFFER_DATE_CHANGE(${a.scheduled_at}, ${a.channel}, day ${a.new_preferred_day})`;
    case "stop":
      return `STOP(${a.stop_reason})`;
    case "abstain":
      return `ABSTAIN(${a.abstain_reason})   [no attempt -- not confident enough to act]`;
    case "escalate_to_human":
      return `ESCALATE_TO_HUMAN(${a.escalate_reason})`;
  }
}

export function whyText(d: DecisionOut): string {
  const a = d.chosen;
  const net = formatInrPrecise(d.rupee_math.expected_net);
  switch (a.action_type) {
    case "schedule_debit":
      return `"Attempt ${d.attempt_index} on ${a.scheduled_at} carries an expected net recovery of ${net}, the best of ${d.rejected_alternatives.length + 1} candidates considered, subject to every HARD compliance clause it satisfies below."`;
    case "offer_date_change":
      return `"Offering a date change to day ${a.new_preferred_day} was the best-scoring candidate."`;
    case "stop":
      return `"No candidate cleared a positive expected net recovery this cycle (${a.stop_reason})."`;
    case "abstain":
      return `"The model's evidence for (${d.bank_id}, ${d.method}) is not trusted enough to act on (${a.abstain_reason}) — no attempt made this cycle. When in doubt, the agent stops rather than guessing or falling back to an unvalidated default."`;
    case "escalate_to_human":
      return `"Handed to a human: ${a.escalate_reason}."`;
  }
}
