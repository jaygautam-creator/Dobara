"use client";

import { useState } from "react";
import { GITHUB_BLOB } from "./nodes";
import type { ComplianceRule } from "@/lib/types";

// docs/10-REDESIGN.md §4: "Below it: the compliance gate as a sequence -- candidate
// actions entering, HARD rules blocking, what survives." The rules are not written here:
// they arrive as props from artifacts/compliance_rules.json, exported straight from
// agent/compliance.py's RULES registry by scripts/build_compliance_rules.py, so this
// panel cannot describe a gate other than the one that runs.
export function ComplianceGateSequence({
  rules,
  nHard,
  nSoft,
}: {
  rules: ComplianceRule[];
  nHard: number;
  nSoft: number;
}) {
  const [openId, setOpenId] = useState<string | null>(null);

  return (
    <div className="grid gap-4 lg:grid-cols-[14rem_minmax(0,1fr)_14rem]">
      <div className="rounded-lg border border-border bg-surface-1 p-4">
        <div className="text-xs font-medium uppercase tracking-wider text-text-muted">
          In
        </div>
        <p className="mt-2 text-sm leading-relaxed text-text-secondary">
          Every legal pairing of an action with a time in the cycle window — one candidate
          per (action, hour, channel) the policy could conceivably choose.
        </p>
      </div>

      <div className="rounded-lg border border-status-critical/40 bg-surface-1 p-4">
        <div className="flex items-baseline justify-between gap-3">
          <div className="text-xs font-medium uppercase tracking-wider text-text-muted">
            The gate
          </div>
          <div className="tabular-nums text-xs text-text-secondary">
            {nHard} HARD · {nSoft} SOFT
          </div>
        </div>
        <p className="mt-2 text-sm leading-relaxed text-text-secondary">
          A HARD rule does not warn or score — a candidate that fails one is removed from
          the set the policy is allowed to choose from. Non-compliance is unrepresentable,
          not discouraged.
        </p>
        <ul className="mt-3 flex flex-wrap gap-1.5">
          {rules.map((rule) => {
            const isOpen = rule.id === openId;
            return (
              <li key={rule.id}>
                <button
                  type="button"
                  onClick={() => setOpenId(isOpen ? null : rule.id)}
                  aria-expanded={isOpen}
                  className={`tabular-nums rounded-full border px-2 py-0.5 text-[11px] transition-colors ${
                    rule.severity === "hard"
                      ? "border-status-critical/40 text-status-critical"
                      : "border-border text-text-secondary"
                  } ${isOpen ? "bg-surface-2" : "hover:bg-surface-2"}`}
                >
                  {rule.id}
                </button>
              </li>
            );
          })}
        </ul>
        {openId && (
          <RuleDetail rule={rules.find((r) => r.id === openId)!} />
        )}
      </div>

      <div className="rounded-lg border border-arm-dobara/40 bg-surface-1 p-4">
        <div className="text-xs font-medium uppercase tracking-wider text-text-muted">
          Out
        </div>
        <p className="mt-2 text-sm leading-relaxed text-text-secondary">
          Only the survivors are scored. The policy takes the argmax of E[net] over that
          set — and if the best survivor is not worth taking, it stops and says which of
          the seven named reasons applies.
        </p>
      </div>
    </div>
  );
}

function RuleDetail({ rule }: { rule: ComplianceRule }) {
  const isUrl = rule.source_url.startsWith("http");
  return (
    <div className="mt-3 rounded-md border border-border bg-surface-0 p-3">
      <div className="flex items-baseline gap-2">
        <span className="tabular-nums text-xs font-semibold text-text-primary">{rule.id}</span>
        <span className="text-[11px] uppercase tracking-wider text-text-muted">
          {rule.severity}
        </span>
      </div>
      <p className="mt-1.5 text-sm leading-relaxed text-text-secondary">{rule.text}</p>
      <p className="mt-2 text-xs text-text-muted">
        {rule.citation} —{" "}
        <a
          href={isUrl ? rule.source_url : `${GITHUB_BLOB}/${rule.source_url}`}
          target="_blank"
          rel="noreferrer"
          className="underline decoration-dotted underline-offset-2"
        >
          {rule.source_url} ↗
        </a>
      </p>
    </div>
  );
}
