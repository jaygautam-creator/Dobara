import { AlertTriangle, CalendarClock, CalendarDays, Pause, Square } from "lucide-react";
import type { DecisionOut } from "@/lib/types";
import { formatInr } from "@/lib/format";
import { ChartDataTable } from "@/components/charts/ChartDataTable";

const VIEW_W = 1000;
const MARGIN_X = 24;
const BAND_H = 64;
const COUNT_H = 46;
const GAP = 28;

type ActionType = DecisionOut["chosen"]["action_type"];

/** One glyph AND one colour per action type -- docs/10-REDESIGN.md §6: "colour is never
 * the only carrier of meaning." The glyph is the primary signal; colour reinforces it. */
const ACTION_GLYPH: Record<ActionType, typeof CalendarClock> = {
  schedule_debit: CalendarClock,
  offer_date_change: CalendarDays,
  stop: Square,
  abstain: Pause,
  escalate_to_human: AlertTriangle,
};

const ACTION_COLOR_VAR: Record<ActionType, string> = {
  schedule_debit: "var(--status-good)",
  offer_date_change: "var(--arm-dobara)",
  stop: "var(--text-muted)",
  abstain: "var(--status-warning)",
  escalate_to_human: "var(--status-critical)",
};

const ACTION_LABEL: Record<ActionType, string> = {
  schedule_debit: "Schedule debit",
  offer_date_change: "Offer date change",
  stop: "Stop",
  abstain: "Abstain",
  escalate_to_human: "Escalate to human",
};

/** A single mandate's full audit trail as one continuous time axis (docs/10-REDESIGN.md
 * §4 `/mandate/[id]`): cycles are labelled bands sharing one real-calendar-time x-scale
 * (not one lane per cycle with its own local axis), attempts are events positioned by
 * their actual `now` timestamp within that shared scale, and each cycle's terminal
 * action gets a visual emphasis ring. A running pre-debit-notification count is drawn
 * beneath the axis on the same x-scale, so restraint (few notices, long gaps) is
 * something a judge sees rather than only reads. Pure server-rendered SVG -- no client
 * JS, no hydration cost across 150 statically generated pages -- native <title>
 * elements provide hover detail without a "use client" boundary. */
export function MandateTimeline({ records }: { records: DecisionOut[] }) {
  const times = records.map((r) => new Date(r.now).getTime());
  const tMin = Math.min(...times);
  const tMax = Math.max(...times);
  const span = tMax - tMin || 1;
  const innerW = VIEW_W - 2 * MARGIN_X;

  function x(t: number): number {
    if (tMax === tMin) return VIEW_W / 2;
    return MARGIN_X + ((t - tMin) / span) * innerW;
  }

  const byCycle = new Map<number, DecisionOut[]>();
  for (const r of records) {
    const list = byCycle.get(r.cycle_index) ?? [];
    list.push(r);
    byCycle.set(r.cycle_index, list);
  }
  const cycles = Array.from(byCycle.keys()).sort((a, b) => a - b);

  // Running count of pre-debit notifications (any chosen action carrying a notice_at)
  // across the whole trail, in chronological order -- the burden the thesis claims to
  // minimise, made visible rather than asserted.
  const notifPoints: { t: number; count: number; hasNotice: boolean }[] = [];
  for (const r of records) {
    const prev = notifPoints.at(-1)?.count ?? 0;
    const hasNotice = !!r.chosen.notice_at;
    notifPoints.push({ t: new Date(r.now).getTime(), count: prev + (hasNotice ? 1 : 0), hasNotice });
  }
  const totalNotifications = notifPoints.at(-1)?.count ?? 0;
  const maxCount = Math.max(1, totalNotifications);

  function yCount(count: number): number {
    return BAND_H + GAP + COUNT_H - (count / maxCount) * (COUNT_H - 6) - 3;
  }

  const stepPath = notifPoints
    .map((p, i) => `${i === 0 ? "M" : "L"}${x(p.t).toFixed(1)},${yCount(p.count).toFixed(1)}`)
    .join(" ");

  const totalH = BAND_H + GAP + COUNT_H + 20;

  const tableRows = records.map((r) => [
    r.cycle_index,
    r.attempt_index,
    ACTION_LABEL[r.chosen.action_type],
    new Date(r.now).toLocaleString("en-IN"),
    r.chosen.notice_at ? new Date(r.chosen.notice_at).toLocaleDateString("en-IN") : "—",
    formatInr(r.expected_net),
  ]);

  return (
    <div className="space-y-3">
      <svg
        viewBox={`0 0 ${VIEW_W} ${totalH}`}
        className="w-full"
        role="img"
        aria-label={`Timeline of ${records.length} decisions across ${cycles.length} cycles, ${totalNotifications} pre-debit notifications sent`}
      >
        {/* cycle bands */}
        {cycles.map((cycle) => {
          const items = byCycle.get(cycle) ?? [];
          const cTimes = items.map((r) => new Date(r.now).getTime());
          const x0 = x(Math.min(...cTimes));
          const x1 = x(Math.max(...cTimes));
          const bandX0 = Math.max(MARGIN_X, x0 - 14);
          const bandX1 = Math.min(VIEW_W - MARGIN_X, Math.max(x1 + 14, x0 + 28));
          return (
            <g key={cycle}>
              <rect
                x={bandX0}
                y={4}
                width={bandX1 - bandX0}
                height={BAND_H - 8}
                rx={6}
                fill="var(--surface-1)"
                stroke="var(--border)"
              />
              <text
                x={bandX0 + 6}
                y={16}
                fontSize={9}
                fontFamily="var(--font-geist-sans)"
                fill="var(--text-muted)"
                letterSpacing="0.04em"
              >
                CYCLE {cycle}
              </text>
            </g>
          );
        })}

        {/* baseline axis */}
        <line
          x1={MARGIN_X}
          y1={BAND_H - 2}
          x2={VIEW_W - MARGIN_X}
          y2={BAND_H - 2}
          stroke="var(--gridline)"
        />

        {/* events */}
        {records.map((r, i) => {
          const cx = x(new Date(r.now).getTime());
          const isTerminal =
            i === records.length - 1 ||
            records[i + 1]?.cycle_index !== r.cycle_index;
          const color = ACTION_COLOR_VAR[r.chosen.action_type];
          const size = isTerminal ? 11 : 8;
          return (
            <g key={i} transform={`translate(${cx - size / 2}, ${28 - size / 2})`}>
              <title>
                {`Cycle ${r.cycle_index}, attempt ${r.attempt_index}: ${ACTION_LABEL[r.chosen.action_type]} — ${new Date(r.now).toLocaleString("en-IN")} — ${formatInr(r.expected_net)}${r.chosen.notice_at ? ` — notice ${new Date(r.chosen.notice_at).toLocaleDateString("en-IN")}` : ""}`}
              </title>
              {isTerminal && (
                <circle
                  cx={size / 2}
                  cy={size / 2}
                  r={size / 2 + 4}
                  fill="none"
                  stroke={color}
                  strokeWidth={1.5}
                  opacity={0.5}
                />
              )}
              <IconGlyph action={r.chosen.action_type} size={size} color={color} />
            </g>
          );
        })}

        {/* running notification count */}
        <text
          x={MARGIN_X}
          y={BAND_H + GAP - 8}
          fontSize={9}
          fill="var(--text-muted)"
          letterSpacing="0.04em"
        >
          PRE-DEBIT NOTIFICATIONS SENT (RUNNING COUNT)
        </text>
        <path d={stepPath} fill="none" stroke="var(--arm-dobara)" strokeWidth={1.5} />
        {notifPoints.map(
          (p, i) =>
            p.hasNotice && (
              <circle
                key={i}
                cx={x(p.t)}
                cy={yCount(p.count)}
                r={2.5}
                fill="var(--arm-dobara)"
              >
                <title>{`Notification ${p.count} of ${totalNotifications}`}</title>
              </circle>
            ),
        )}
        <text
          x={VIEW_W - MARGIN_X}
          y={BAND_H + GAP - 8}
          fontSize={11}
          textAnchor="end"
          fontFamily="var(--font-geist-mono)"
          fill="var(--text-primary)"
        >
          total {totalNotifications}
        </text>
      </svg>

      <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-[11px] text-text-muted">
        {(Object.keys(ACTION_LABEL) as ActionType[]).map((a) => (
          <span key={a} className="inline-flex items-center gap-1">
            <IconGlyph action={a} size={11} color={ACTION_COLOR_VAR[a]} inline />
            {ACTION_LABEL[a]}
          </span>
        ))}
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-[7px] w-[7px] rounded-full ring-1 ring-offset-1 ring-offset-surface-0" />
          ring = terminal action of its cycle
        </span>
      </div>

      <ChartDataTable
        caption={`Full decision trail for this mandate, ${records.length} rows`}
        columns={["Cycle", "Attempt", "Action", "Decided at", "Notice date", "E[net]"]}
        rows={tableRows}
      />
    </div>
  );
}

function IconGlyph({
  action,
  size,
  color,
  inline,
}: {
  action: ActionType;
  size: number;
  color: string;
  inline?: boolean;
}) {
  const Glyph = ACTION_GLYPH[action];
  return <Glyph width={size} height={size} color={color} strokeWidth={inline ? 2.25 : 2.5} />;
}
