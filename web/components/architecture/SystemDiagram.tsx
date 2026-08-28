"use client";

import { useState } from "react";
import { BOUNDARY_TEST, GITHUB_BLOB, NODES, type DiagramNode } from "./nodes";

// docs/10-REDESIGN.md §4 `/architecture`: "Draw the LLM boundary as a literal wall."
// The money path runs left to right across the top; the narrative lane sits below the
// wall; the one arrow that tries to cross upward is drawn stopped, with the test that
// stops it named on the wall itself. Pure SVG + React state, no runtime data, so the
// static export renders it identically with no server.
const VIEWBOX = { w: 1000, h: 476 };
const WALL_Y = 300;

const MONEY_EDGES: [string, string][] = [
  ["sim", "features"],
  ["features", "models"],
  ["models", "policy"],
  ["policy", "gate"],
  ["gate", "action"],
  ["action", "audit"],
  ["audit", "harness"],
];

/** SVG <text> does not wrap, and a sublabel that overruns its box silently slides under
 * the neighbouring node. Splits on words to fit the node's own width (Geist's ~5.4px per
 * character at 11px), at most two lines. */
function wrapSublabel(text: string, width: number): string[] {
  const maxChars = Math.floor((width - 28) / 5.4);
  const lines: string[] = [];
  let current = "";
  for (const word of text.split(" ")) {
    const candidate = current ? `${current} ${word}` : word;
    if (candidate.length <= maxChars || !current) {
      current = candidate;
    } else {
      lines.push(current);
      current = word;
    }
  }
  if (current) lines.push(current);
  return lines.slice(0, 2);
}

function nodeById(id: string): DiagramNode {
  const node = NODES.find((n) => n.id === id);
  if (!node) throw new Error(`unknown diagram node ${id}`);
  return node;
}

/** Anchor points on a node's box, chosen by where the two boxes sit relative to each
 * other -- keeps every connector orthogonal-ish without hand-placing 7 paths. */
function edgePath(from: DiagramNode, to: DiagramNode): string {
  const fx = from.x + from.w;
  const fy = from.y + from.h / 2;
  const tx = to.x;
  const ty = to.y + to.h / 2;
  if (Math.abs(fy - ty) < 4) return `M ${fx} ${fy} L ${tx} ${ty}`;
  // Drop down (or up) and come back: gate -> action wraps a row.
  const midY = (from.y + from.h + to.y) / 2;
  const startX = from.x + from.w / 2;
  const endX = to.x + to.w / 2;
  return `M ${startX} ${from.y + from.h} L ${startX} ${midY} L ${endX} ${midY} L ${endX} ${to.y}`;
}

export function SystemDiagram() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = selectedId ? nodeById(selectedId) : null;

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <div className="overflow-x-auto rounded-lg border border-border bg-surface-1 p-3">
        <svg
          viewBox={`0 0 ${VIEWBOX.w} ${VIEWBOX.h}`}
          className="h-auto w-full min-w-[46rem]"
          role="img"
          aria-label="Dobara system diagram: a money path of tabular, calibrated components crossing a compliance gate to a bounded action set, and a separate narrative lane containing the LLM layer, which cannot cross into the money path."
        >
          <defs>
            <marker
              id="arrow"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--arm-dobara)" />
            </marker>
            <marker
              id="arrow-muted"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--text-muted)" />
            </marker>
          </defs>

          {MONEY_EDGES.map(([fromId, toId]) => (
            <path
              key={`${fromId}-${toId}`}
              d={edgePath(nodeById(fromId), nodeById(toId))}
              fill="none"
              stroke="var(--arm-dobara)"
              strokeWidth={1.5}
              markerEnd="url(#arrow)"
            />
          ))}

          {/* Permitted, one-way: a decision that has already been made is handed down to
              be described. */}
          <path
            d={`M ${nodeById("audit").x + 40} ${nodeById("audit").y + nodeById("audit").h} L ${nodeById("audit").x + 40} ${WALL_Y - 14} L ${nodeById("llm").x + nodeById("llm").w / 2} ${WALL_Y + 14} L ${nodeById("llm").x + nodeById("llm").w / 2} ${nodeById("llm").y}`}
            fill="none"
            stroke="var(--text-muted)"
            strokeWidth={1.25}
            strokeDasharray="4 3"
            markerEnd="url(#arrow-muted)"
          />
          <text
            x={VIEWBOX.w - 12}
            y={WALL_Y - 26}
            textAnchor="end"
            className="fill-[var(--text-muted)] text-[11px]"
          >
            decisions, already made, handed down to be described
          </text>

          {/* The wall. */}
          <line
            x1={0}
            y1={WALL_Y}
            x2={VIEWBOX.w}
            y2={WALL_Y}
            stroke="var(--status-critical)"
            strokeWidth={3}
          />
          <text x={12} y={WALL_Y - 10} className="fill-[var(--status-critical)] text-[13px] font-semibold">
            The LLM boundary — money decisions cannot cross
          </text>
          <text
            x={VIEWBOX.w - 12}
            y={WALL_Y + 20}
            textAnchor="end"
            className="fill-[var(--text-muted)] font-mono text-[11px]"
          >
            enforced by {BOUNDARY_TEST}, not by a prompt
          </text>

          {/* The blocked crossing: the LLM lane trying to reach the policy. */}
          <path
            d={`M ${nodeById("llm").x + 24} ${nodeById("llm").y} L ${nodeById("llm").x + 24} ${WALL_Y + 12}`}
            fill="none"
            stroke="var(--status-critical)"
            strokeWidth={1.5}
            strokeDasharray="5 4"
          />
          <g transform={`translate(${nodeById("llm").x + 24} ${WALL_Y + 8})`}>
            <circle r={9} fill="var(--surface-1)" stroke="var(--status-critical)" strokeWidth={1.5} />
            <path d="M -4 -4 L 4 4 M 4 -4 L -4 4" stroke="var(--status-critical)" strokeWidth={1.5} />
          </g>

          {NODES.map((node) => {
            const isSelected = node.id === selectedId;
            const stroke =
              node.lane === "money"
                ? isSelected
                  ? "var(--arm-dobara)"
                  : "var(--border)"
                : isSelected
                  ? "var(--text-secondary)"
                  : "var(--border)";
            return (
              // Deliberately not animated in: a staggered fade on ten static boxes is
              // decoration, which docs/10-REDESIGN.md §5 rules out -- and because
              // `staticRender` can only be known on the client, animating here made the
              // server and client markup disagree (a real hydration mismatch, caught in
              // the dev overlay during this session's screenshot pass).
              <g
                key={node.id}
                role="button"
                tabIndex={0}
                aria-pressed={isSelected}
                aria-label={`${node.label}: ${node.sublabel}`}
                className="cursor-pointer outline-none [&:focus-visible>rect]:stroke-[var(--ring)] [&:focus-visible>rect]:stroke-2"
                onClick={() => setSelectedId(isSelected ? null : node.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setSelectedId(isSelected ? null : node.id);
                  }
                }}
              >
                <rect
                  x={node.x}
                  y={node.y}
                  width={node.w}
                  height={node.h}
                  rx={8}
                  fill={isSelected ? "var(--surface-2)" : "var(--surface-0)"}
                  stroke={stroke}
                  strokeWidth={isSelected ? 2 : 1}
                />
                {node.lane === "money" && (
                  <rect x={node.x} y={node.y} width={3} height={node.h} rx={1.5} fill="var(--arm-dobara)" />
                )}
                <text x={node.x + 14} y={node.y + 22} className="fill-[var(--text-primary)] text-[14px] font-semibold">
                  {node.label}
                </text>
                {wrapSublabel(node.sublabel, node.w).map((line, li) => (
                  <text
                    key={line}
                    x={node.x + 14}
                    y={node.y + 40 + li * 14}
                    className="fill-[var(--text-secondary)] text-[11px]"
                  >
                    {line}
                  </text>
                ))}
                <text x={node.x + 14} y={node.y + 72} className="fill-[var(--text-muted)] font-mono text-[10px]">
                  {node.file.replace(/^web\//, "")}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <aside className="rounded-lg border border-border bg-surface-1 p-5" aria-live="polite">
        {selected ? (
          <>
            <div className="text-xs font-medium uppercase tracking-wider text-text-muted">
              {selected.lane === "money" ? "Money path" : "Narrative lane"}
            </div>
            <h3 className="mt-1 text-step-2 font-semibold text-text-primary">{selected.label}</h3>
            <p className="mt-3 text-sm leading-relaxed text-text-secondary">{selected.description}</p>
            <a
              href={`${GITHUB_BLOB}/${selected.file}`}
              target="_blank"
              rel="noreferrer"
              className="mt-4 inline-block font-mono text-xs text-arm-dobara underline decoration-dotted underline-offset-2"
            >
              {selected.file} ↗
            </a>
          </>
        ) : (
          <>
            <div className="text-xs font-medium uppercase tracking-wider text-text-muted">
              The one claim worth checking
            </div>
            <h3 className="mt-1 text-step-2 font-semibold text-text-primary">
              No money decision passes through a language model.
            </h3>
            <p className="mt-3 text-sm leading-relaxed text-text-secondary">
              Everything above the red line is tabular, calibrated and inspectable: the
              probability of a debit succeeding, the hazard of the mandate being revoked,
              the remaining lifetime value, and the arithmetic that trades them off. The
              language model sits below the line and is handed decisions that have already
              been made, to describe them.
            </p>
            <p className="mt-3 text-sm leading-relaxed text-text-secondary">
              That separation is a test, not a promise —{" "}
              <a
                href={`${GITHUB_BLOB}/${BOUNDARY_TEST}`}
                target="_blank"
                rel="noreferrer"
                className="font-mono text-xs text-arm-dobara underline decoration-dotted underline-offset-2"
              >
                {BOUNDARY_TEST} ↗
              </a>{" "}
              fails the build if an import ever crosses it.
            </p>
            <p className="mt-4 text-xs text-text-muted">
              Select any box to see what it owns and open its source.
            </p>
          </>
        )}
      </aside>
    </div>
  );
}
