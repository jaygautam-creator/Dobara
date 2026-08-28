"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { motion, useInView } from "motion/react";
import { useStaticRender } from "@/lib/motion";
import { formatInr, formatNumber } from "@/lib/format";
import type { HomeDemoEvent, HomeDemoJson, HomeDemoLane } from "@/lib/types";

// docs/10-REDESIGN.md §4 `/` beat 2 -- "the highest-value single element on the site".
// One real mandate, replayed under two policies, beat by beat. Every event, timestamp,
// counter and rupee figure here comes from artifacts/home_demo.json, which
// scripts/build_home_demo.py writes from eval.runner's own trace of the same run the
// evidence pipeline scores: nothing on this page is authored, re-ordered or rounded by
// hand. The two lanes advance on one shared clock, so the aggressive lane visibly races
// ahead of the restrained one instead of the two being merely juxtaposed.

const BEAT_MS = 300;

interface Beat {
  lane: "aggressive_8x" | "dobara";
  order: number;
  event: HomeDemoEvent;
}

const LANE_META = {
  aggressive_8x: {
    title: "The standard playbook",
    subtitle: "aggressive_8x — retry up to 8 times a cycle",
    accent: "var(--arm-aggressive-8x)",
  },
  dobara: {
    title: "Dobara",
    subtitle: "retry while the bet is positive, then stop",
    accent: "var(--arm-dobara)",
  },
} as const;

function formatAt(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

/** What actually happened on this beat, in the plainest words that stay true to the
 * event's own fields -- never a summary the trace doesn't support. */
function describe(event: HomeDemoEvent): string {
  if (event.kind === "attempt") {
    const outcome =
      event.outcome === "success"
        ? "debit succeeded"
        : event.outcome === "hard_decline"
          ? "hard decline"
          : event.outcome === "soft_decline"
            ? "insufficient balance"
            : (event.outcome ?? "attempted");
    return `Pre-debit notice sent, debit attempted — ${outcome}${
      event.revoked ? " — the customer cancels the mandate" : ""
    }`;
  }
  if (event.kind === "offer_date_change") return "Offered to move the debit date permanently";
  if (event.kind === "stop") return `Stopped — ${event.reason?.replaceAll("_", " ")}`;
  if (event.kind === "abstain") return `Abstained — ${event.reason?.replaceAll("_", " ")}`;
  return `Escalated to a human — ${event.reason ?? "reason recorded in the audit trail"}`;
}

export function Demonstration({ demo }: { demo: HomeDemoJson }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.25 });

  // Both lanes' full recorded lifetimes, merged onto one clock and ordered by the moment
  // each beat happened -- so the aggressive lane visibly burns through its attempts and
  // dies while the restrained lane is still waiting, and the restrained lane's later
  // cycles (the ones the revoked mandate never gets to have) are visible as the payoff.
  const beats = useMemo(() => {
    const collect = (lane: "aggressive_8x" | "dobara") =>
      demo.lanes[lane].events.map((event) => ({ lane, event }));
    const merged = [...collect("aggressive_8x"), ...collect("dobara")].sort(
      (a, b) => a.event.at.localeCompare(b.event.at),
    );
    return merged.map((b, i) => ({ ...b, order: i })) as Beat[];
  }, [demo]);

  const total = beats.length;
  const isStatic = useStaticRender();
  const [liveStep, setStep] = useState(0);
  // A reduced-motion visitor and a `?static=1` screenshot capture get the completed end
  // state immediately, per docs/10-REDESIGN.md §5 -- not a sequence they cannot see.
  const step = isStatic ? total : liveStep;

  useEffect(() => {
    if (isStatic || !inView || liveStep >= total) return;
    const timer = setTimeout(() => setStep((s) => s + 1), BEAT_MS);
    return () => clearTimeout(timer);
  }, [isStatic, inView, liveStep, total]);

  const done = step >= total;

  return (
    <div
      ref={ref}
      className="space-y-4"
      // docs/10-REDESIGN.md §5: never make a judge wait. Anywhere in the demonstration
      // completes it instantly; the button then offers a replay.
      onClick={() => {
        if (!done) setStep(total);
      }}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <p className="text-sm leading-relaxed text-text-secondary">
          One mandate —{" "}
          <span className="tabular-nums">#{demo.mandate.mandate_id}</span>,{" "}
          {demo.mandate.merchant_category}, {demo.mandate.bank_id},{" "}
          <span className="tabular-nums">{formatInr(demo.mandate.amount)}</span> a cycle —
          run twice.
        </p>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setStep(done ? 0 : total);
          }}
          disabled={isStatic}
          className="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-1 hover:text-text-primary"
        >
          {done ? "Replay" : "Skip to the end"}
        </button>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {(["aggressive_8x", "dobara"] as const).map((lane) => (
          <LaneColumn
            key={lane}
            lane={lane}
            data={demo.lanes[lane]}
            beats={beats.filter((b) => b.lane === lane)}
            step={step}
          />
        ))}
      </div>
    </div>
  );
}

function LaneColumn({
  lane,
  data,
  beats,
  step,
}: {
  lane: "aggressive_8x" | "dobara";
  data: HomeDemoLane;
  beats: Beat[];
  step: number;
}) {
  const meta = LANE_META[lane];
  const revealed = beats.filter((b) => b.order < step);
  const revoked = revealed.some((b) => b.event.revoked);
  const notifications = revealed.length
    ? revealed[revealed.length - 1].event.notifications_to_date
    : 0;
  const finished = revealed.length === beats.length;
  // The honest framing of the counter: the revoked lane sends fewer messages in total
  // only because it has no mandate left to message. Days elapsed says so without
  // editorialising -- both numbers are read off the beats themselves.
  const spanDays =
    revealed.length > 1
      ? Math.round(
          (new Date(revealed[revealed.length - 1].event.at).getTime() -
            new Date(revealed[0].event.at).getTime()) /
            86_400_000,
        )
      : 0;

  return (
    <div
      className={`rounded-lg border bg-surface-1 p-5 transition-opacity duration-500 ${
        revoked ? "border-status-critical/40 opacity-70" : "border-border"
      }`}
    >
      <div className="flex items-baseline justify-between gap-3">
        <div>
          <div
            className="text-sm font-semibold"
            style={{ color: meta.accent }}
          >
            {meta.title}
          </div>
          <div className="text-xs text-text-muted">{meta.subtitle}</div>
        </div>
        <div className="text-right">
          <div className="tabular-nums text-step-3 font-semibold text-text-primary">
            {formatNumber(notifications)}
          </div>
          <div className="text-[11px] uppercase tracking-wider text-text-muted">
            mandatory messages
          </div>
          <div className="tabular-nums text-[11px] text-text-muted">
            in {formatNumber(spanDays)} days
          </div>
        </div>
      </div>

      <ol className="mt-4 space-y-1.5">
        {beats.map((beat) => {
          const shown = beat.order < step;
          return (
            <motion.li
              key={`${beat.lane}-${beat.order}`}
              initial={false}
              animate={{ opacity: shown ? 1 : 0.12, x: shown ? 0 : -4 }}
              transition={{ duration: 0.22, ease: [0.2, 0, 0, 1] }}
              className={`flex items-baseline gap-3 rounded-md px-2 py-1.5 text-xs ${
                beat.event.revoked
                  ? "bg-status-critical/10"
                  : beat.event.kind === "stop"
                    ? "bg-arm-dobara/10"
                    : ""
              }`}
            >
              <span className="tabular-nums w-24 shrink-0 text-text-muted">
                {formatAt(beat.event.at)}
              </span>
              <span className="tabular-nums w-14 shrink-0 text-text-muted">
                cycle {beat.event.cycle_index}
              </span>
              <span
                className={
                  beat.event.revoked
                    ? "text-status-critical"
                    : beat.event.kind === "stop"
                      ? "text-arm-dobara"
                      : "text-text-secondary"
                }
              >
                {describe(beat.event)}
              </span>
            </motion.li>
          );
        })}
      </ol>

      {finished && (
        <motion.div
          initial={false}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: [0.2, 0, 0, 1] }}
          className={`mt-4 rounded-md border p-3 ${
            revoked ? "border-status-critical/40" : "border-arm-dobara/40"
          }`}
        >
          <div
            className={`text-sm font-semibold ${
              revoked ? "text-status-critical" : "text-arm-dobara"
            }`}
          >
            {revoked
              ? `Mandate revoked in cycle ${data.totals.revoked_at_cycle}`
              : "Mandate still alive"}
          </div>
          <p className="mt-1 text-xs leading-relaxed text-text-secondary">
            {revoked ? (
              <>
                Every future cycle of this mandate is gone with it:{" "}
                <span className="tabular-nums">{formatInr(data.totals.ltv_lost_inr)}</span> of
                remaining lifetime value forgone, against{" "}
                <span className="tabular-nums">
                  {formatInr(data.totals.gross_recovered_inr)}
                </span>{" "}
                recovered over the whole run.
              </>
            ) : (
              <>
                <span className="tabular-nums">
                  {formatInr(data.totals.gross_recovered_inr)}
                </span>{" "}
                recovered over the whole run with no lifetime value forgone — net{" "}
                <span className="tabular-nums">{formatInr(data.totals.net_ltv_inr)}</span>{" "}
                against this mandate.
              </>
            )}
          </p>
        </motion.div>
      )}
    </div>
  );
}
