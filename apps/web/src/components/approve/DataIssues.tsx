import type { DataIssue } from "@/lib/run";
import { placeName } from "@/lib/stores";

export function DataIssues({ issues }: { issues: DataIssue[] }) {
  return (
    <section aria-labelledby="data-issues-title" className="mx-auto w-full max-w-[1240px] px-4 pt-12 md:px-8 md:pt-16">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="data-issues-title" className="font-serif text-[28px] leading-tight md:text-[32px]">
          Data issues
        </h2>
        <p className="text-[13px] text-stone">Rows the engine did not trust, so no move uses them.</p>
      </div>
      {issues.length === 0 ? (
        <p className="mt-4 rounded-xl border border-rule bg-white px-5 py-4 text-sm text-stone">
          No data issues in this run.
        </p>
      ) : (
        <ul className="mt-4 grid gap-3 md:grid-cols-2">
          {issues.map((issue) => (
            <li key={`${issue.location_id}-${issue.sku_id}`} className="rounded-xl border border-rule bg-white px-5 py-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold tabular-nums">
                  {issue.location_id} · {issue.sku_id}
                </span>
                <span className="text-xs text-stone">{placeName(issue.location_id)}</span>
                {issue.excluded && (
                  <span className="ml-auto rounded-full bg-oxblood/8 px-2 py-0.5 text-[11px] font-semibold text-oxblood">
                    Excluded from moves
                  </span>
                )}
              </div>
              <p className="mt-2 text-sm text-stone">{issue.note}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
