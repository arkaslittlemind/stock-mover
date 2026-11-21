import { formatDate, formatINR, priorityOf, TYPE_LABEL } from "@/lib/format";
import type { Move } from "@/lib/run";
import { placeName } from "@/lib/stores";
import { RouteArrow } from "./RouteArrow";

/** Boarding-pass card for the run's highest-priority move. */
export function HeroTicket({ move }: { move: Move | null }) {
  if (!move) {
    return (
      <div className="rounded-[14px] bg-white p-8 text-center shadow-[0_0_0_1px_rgba(39,33,30,0.08),0_24px_56px_-28px_rgba(39,33,30,0.35)]">
        <p className="font-serif text-3xl">No moves today</p>
        <p className="mt-2 text-sm text-stone">Every store has the stock it needs for now.</p>
      </div>
    );
  }

  const p = priorityOf(move);
  const tag = [p.label, move.needs_senior_approval ? "Senior approval" : null].filter(Boolean).join(" · ");

  return (
    <article
      aria-label="Top recommended move"
      className="rounded-[14px] bg-white shadow-[0_0_0_1px_rgba(39,33,30,0.08),0_1px_2px_rgba(39,33,30,0.06),0_24px_56px_-28px_rgba(39,33,30,0.35)] motion-safe:animate-ticket-in"
    >
      <div className="rounded-t-[14px] bg-charcoal px-[18px] pt-[18px] pb-5 text-ivory md:px-[22px]">
        <div className="flex items-center justify-between gap-2 text-xs">
          <span className="rounded-full bg-ivory/12 px-2 py-[3px] font-medium">{TYPE_LABEL[move.type]}</span>
          <span className="font-semibold text-[#f0b9c4]">{tag}</span>
        </div>
        <div className="mt-[18px] flex items-center justify-between gap-3">
          <div className="flex flex-col">
            <span className="text-[28px] leading-none font-semibold tracking-[-0.01em] whitespace-nowrap tabular-nums md:text-[42px]">
              {move.from}
            </span>
            <span className="mt-1.5 text-[13px] text-ivory/65">{placeName(move.from)}</span>
          </div>
          <RouteArrow width={96} className="min-w-10 flex-1 text-saffron" />
          <div className="flex flex-col text-right">
            <span className="text-[28px] leading-none font-semibold tracking-[-0.01em] whitespace-nowrap tabular-nums md:text-[42px]">
              {move.to}
            </span>
            <span className="mt-1.5 text-[13px] text-ivory/65">{placeName(move.to)}</span>
          </div>
        </div>
      </div>
      <div className="ticket-perforation" aria-hidden="true" />
      <div className="px-[18px] pt-[18px] pb-5 md:px-[22px]">
        <dl className="grid grid-cols-2 gap-x-5 gap-y-3.5 tabular-nums sm:grid-cols-4 [&_dt]:text-[11px] [&_dt]:font-medium [&_dt]:tracking-[0.06em] [&_dt]:text-stone [&_dt]:uppercase [&_dd]:mt-0.5 [&_dd]:text-[15px] [&_dd]:font-semibold">
          <div className="col-span-full">
            <dt>Style</dt>
            <dd>
              {move.style_name} <span className="font-normal text-stone">· {move.sku_id}</span>
            </dd>
          </div>
          <div>
            <dt>Size</dt>
            <dd>{move.size}</dd>
          </div>
          <div>
            <dt>Units</dt>
            <dd className="!text-[28px] leading-[1.05] text-oxblood">{move.units}</dd>
          </div>
          <div>
            <dt>Value</dt>
            <dd>{formatINR(move.value_mrp)}</dd>
          </div>
          <div>
            <dt>Arrives</dt>
            <dd>{formatDate(move.arrives_on)}</dd>
          </div>
        </dl>
        <p className="mt-3.5 border-l-2 border-saffron bg-ivory px-3 py-2.5 text-[13px]">{move.reason}</p>
      </div>
    </article>
  );
}
