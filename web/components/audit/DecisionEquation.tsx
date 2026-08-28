import type { ReactNode } from "react";
import type { RupeeMathOut } from "@/lib/types";
import { formatInrPrecise, formatPct } from "@/lib/format";

/** The same `E[net | action]` expression `components/home/Equation.tsx` shows on `/`,
 * instantiated here for one real decision -- docs/10-REDESIGN.md §4 `/audit/[id]`: "the
 * rupee maths shown as a worked equation with real numbers substituted in." Every figure
 * comes from this decision's own `rupee_math`, never re-derived or rounded differently
 * than the term-by-term grid above it. Static (no client JS): this page is one of 1,296
 * statically generated, and the annotation-on-hover interactivity already lives on `/`. */
export function DecisionEquation({ rm }: { rm: RupeeMathOut }) {
  const gain = rm.p_success * rm.amount;
  const loss = rm.p_revoke * rm.ltv_remaining;
  return (
    <div className="tabular-nums space-y-1 text-xs leading-relaxed">
      <Row label="E[net]" value="P(success) × amount − P(revoke) × LTV_remaining − cost(channel)" muted />
      <Row
        value={
          <>
            <span className="text-status-good-text">
              {formatPct(rm.p_success, 2)} × {formatInrPrecise(rm.amount)}
            </span>{" "}
            <span className="text-text-secondary">−</span>{" "}
            <span className="text-status-critical-text">
              {formatPct(rm.p_revoke, 3)} × {formatInrPrecise(rm.ltv_remaining)}
            </span>{" "}
            <span className="text-text-secondary">−</span>{" "}
            <span className="text-text-secondary">{formatInrPrecise(rm.cost)}</span>
          </>
        }
      />
      <Row
        value={
          <>
            <span className="text-status-good-text">{formatInrPrecise(gain)}</span>{" "}
            <span className="text-text-secondary">−</span>{" "}
            <span className="text-status-critical-text">{formatInrPrecise(loss)}</span>{" "}
            <span className="text-text-secondary">−</span>{" "}
            <span className="text-text-secondary">{formatInrPrecise(rm.cost)}</span>
          </>
        }
      />
      <Row
        value={
          <span
            className={`font-semibold ${rm.expected_net >= 0 ? "text-status-good-text" : "text-status-critical-text"}`}
          >
            = {formatInrPrecise(rm.expected_net)}
          </span>
        }
      />
    </div>
  );
}

function Row({
  label,
  value,
  muted,
}: {
  label?: string;
  value: ReactNode;
  muted?: boolean;
}) {
  return (
    <div className="flex items-baseline gap-2 pl-2">
      <span className="w-4 shrink-0" />
      <span className={muted ? "text-text-muted" : ""}>
        {label && <span className="mr-1 text-text-muted">{label} =</span>}
        {value}
      </span>
    </div>
  );
}
