/** The `/audit` "ask why" box (docs/08-FRONTEND-SPEC.md). Static export has no server,
 * so there is no runtime to hold an API key or make an LLM call on the deployed site --
 * every narrative here was generated ahead of time, offline, from this exact decision's
 * structured audit record, by `scripts/generate_ask_why.py` (`make ask-why`), and
 * committed to `artifacts/llm_cache/ask_why.json`. That's stated in the UI rather than
 * hidden: the architecture's central claim -- narrative and money never share a
 * pipeline -- is more convincing shown than merely asserted. See llm/narrate.py for the
 * prompt, which is instructed to explain the record, never to add to or second-guess it.
 *
 * Renders nothing when the cache has no entry for this decision (absent cache file, or
 * a batch run that hadn't reached this key yet) -- an empty "ask why" box would be worse
 * than no box, and the rest of the audit record already stands on its own. */
export function AskWhyBox({ narrative }: { narrative: string | null }) {
  if (!narrative) return null;
  return (
    <details className="rounded-md border border-border bg-surface-0 p-3 text-xs">
      <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-text-muted">
        Ask why
      </summary>
      <p className="mt-2 text-sm leading-relaxed text-text-secondary">{narrative}</p>
      <p className="mt-2 text-[11px] text-text-muted">
        Generated ahead of time from the structured audit record above, by a model that
        never touched the money decision.
      </p>
    </details>
  );
}
