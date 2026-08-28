import type { ReactNode } from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

/** A text/table alternative for a chart's data -- docs/10-REDESIGN.md §6: "charts have a
 * text alternative or an accessible data table." Collapsed by default behind native
 * `<details>` (not the shadcn accordion -- that component is reserved for content the
 * spec explicitly allows hiding; a chart's own numeric backing is not the honesty panel
 * and is fine to fold, but `<details>` keeps it keyboard-operable and in the
 * accessibility tree with zero extra JS). */
export function ChartDataTable({
  caption,
  columns,
  rows,
}: {
  caption: string;
  columns: string[];
  rows: (string | number)[][];
}) {
  return (
    <details className="group mt-2 text-xs">
      <summary className="w-fit cursor-pointer select-none rounded text-text-muted underline decoration-dotted underline-offset-2 hover:text-text-secondary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-arm-dobara">
        View chart data as a table
      </summary>
      <div className="mt-2 max-h-72 overflow-auto rounded-md border border-border">
        <Table>
          <caption className="sr-only">{caption}</caption>
          <TableHeader>
            <TableRow>
              {columns.map((c) => (
                <TableHead key={c} className="tabular-nums">
                  {c}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row, i) => (
              <TableRow key={i}>
                {row.map((cell, j) => (
                  <TableCell key={j} className="tabular-nums">
                    {cell as ReactNode}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </details>
  );
}
