import { formatNum } from "@/lib/format";
import type { Run } from "@/lib/run";

export function StoreHealthStrip({ stores }: { stores: Run["stores"] }) {
  if (stores.length === 0) return null;

  const underStocked = stores.filter((store) => store.flags.includes("under_stocked")).length;
  const overCapacity = stores.filter((store) => store.flags.includes("over_capacity")).length;

  return (
    <section aria-label="Store health" className="mx-auto mb-6 w-full max-w-[1200px] px-4 md:px-6">
      <details className="rounded-xl border border-rule bg-white/35">
        <summary className="cursor-pointer rounded-xl px-4 py-3 font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-saffron">
          Store health{" "}
          <span className="ml-2 text-sm font-normal text-stone tabular-nums">
            {stores.length} stores · {underStocked} under-stocked
            {overCapacity > 0 && ` · ${overCapacity} still over capacity`}
          </span>
        </summary>
        <p className="border-t border-rule px-4 py-3 text-sm text-stone">
          Stock as of the snapshot, including units already in transit.
        </p>
        <ul className="grid gap-px overflow-hidden rounded-b-xl bg-rule sm:grid-cols-2 lg:grid-cols-4">
          {stores.map((store) => (
            <li key={store.store_id} className="min-w-0 bg-ivory p-4 text-sm">
              <h3 className="font-semibold">{store.store_id} · {store.city}</h3>
              <p className="mt-1 text-stone tabular-nums">
                {formatNum(store.units_on_hand + store.units_in_transit)} of {formatNum(store.capacity_units)}
                {" units · "}{store.fill_pct}% full
              </p>
              <p className="text-stone tabular-nums">
                {store.days_of_cover === null ? "Cover unavailable" : `${store.days_of_cover.toFixed(1)} days of cover`}
              </p>
              {store.flags.includes("under_stocked") && <p className="mt-1 font-medium text-oxblood">Under-stocked</p>}
              {store.flags.includes("over_capacity") && <p className="mt-1 font-medium text-oxblood">Still over capacity after planned moves</p>}
              {store.min_display_gaps.length > 0 && (
                <ul aria-label="Minimum display gaps" className="mt-2 space-y-1 text-stone">
                  {store.min_display_gaps.map((gap) => (
                    <li key={gap.category}>{gap.category} · {gap.gap} below minimum</li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      </details>
    </section>
  );
}
