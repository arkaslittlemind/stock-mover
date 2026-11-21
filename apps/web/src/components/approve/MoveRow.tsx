"use client";

import { memo } from "react";
import type { Decision } from "@/lib/approvals";
import { formatDate, formatINR, priorityOf, TONE_TEXT } from "@/lib/format";
import type { Move } from "@/lib/run";
import { cn } from "@/lib/utils";
import { RouteArrow } from "./RouteArrow";

export const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-saffron";


type Props = {
  move: Move;
  decision: Decision | undefined;
  expanded: boolean;
  onDecide: (id: string, d: Decision) => void;
  onToggle: (id: string) => void;
};

function fmtCover(v: number | null) {
  return v === null ? "n/a" : `${v.toFixed(1)} days`;
}

export const MoveRow = memo(function MoveRow({ move: m, decision, expanded, onDecide, onToggle }: Props) {
  const p = priorityOf(m);
  const detailsId = `details-${m.id}`;
  const dim = decision === "rejected" ? "opacity-45" : "";

  return (
    <li
      data-decision={decision}
      className={cn(
        "grid gap-x-3 gap-y-2 border-b border-rule px-4 py-3.5 transition-colors duration-150",
        "grid-cols-[minmax(0,1fr)_auto] [grid-template-areas:'prio_units''style_style''route_value''actions_actions''details_details']",
        `min-[1100px]:grid-cols-[92px_minmax(0,1fr)_160px_40px_84px_176px] min-[1100px]:items-center min-[1100px]:gap-x-3.5 min-[1100px]:px-5 min-[1100px]:py-3 min-[1100px]:[grid-template-areas:'prio_style_route_units_value_actions''details_details_details_details_details_details']`,
        decision === "approved" && "bg-approve/6",
        decision !== "approved" && "hover:bg-[#fcfaf6]",
      )}
    >
      <span className={cn("inline-flex items-center gap-1.5 text-xs font-semibold [grid-area:prio]", TONE_TEXT[p.tone], dim)}>
        <i className="size-2 rounded-[2px] bg-current" aria-hidden="true" />
        {p.label}
      </span>

      <div className={cn("min-w-0 [grid-area:style]", dim)}>
        <p className={`font-semibold min-[1100px]:truncate`}>{m.style_name}</p>
        <p className="text-xs text-stone">
          {m.sku_id} · {m.size}
          {m.needs_senior_approval && <span className="font-medium text-oxblood"> · Senior approval</span>}
        </p>
        <p className={cn("mt-0.5 text-xs text-stone", !expanded && "line-clamp-2")} title={expanded ? undefined : m.reason}>
          {m.reason}
        </p>
        <button
          type="button"
          aria-expanded={expanded}
          aria-controls={detailsId}
          onClick={() => onToggle(m.id)}
          className={cn("mt-1 text-xs font-medium text-oxblood underline-offset-2 hover:underline", FOCUS)}
        >
          {expanded ? "Hide numbers" : "Details"}
        </button>
      </div>

      <span className={cn("inline-flex items-center gap-1.5 whitespace-nowrap text-base font-semibold tabular-nums [grid-area:route] min-[1100px]:text-sm", dim)}>
        {m.from}
        <RouteArrow width={24} className="text-oxblood" />
        {m.to}
      </span>

      <span className={cn("text-right text-lg font-semibold tabular-nums [grid-area:units]", dim)}>
        {m.units}
        <span className={`text-xs font-normal text-stone min-[1100px]:hidden`}> units</span>
      </span>

      <span className={cn("text-right text-stone tabular-nums [grid-area:value]", dim)}>{formatINR(m.value_mrp)}</span>

      <div className={`flex gap-1.5 [grid-area:actions] min-[1100px]:justify-end`}>
        <button
          type="button"
          aria-pressed={decision === "approved"}
          aria-label={`Approve ${m.units} of ${m.sku_id} from ${m.from} to ${m.to}`}
          onClick={() => onDecide(m.id, "approved")}
          className={cn(
            "inline-flex h-11 flex-1 items-center justify-center gap-1.5 rounded-lg border px-2.5 text-[13px] font-medium transition-[background-color,border-color,color,transform] duration-150 active:scale-[0.97]",
            `min-[1100px]:h-8 min-[1100px]:flex-none`,
            FOCUS,
            decision === "approved"
              ? "border-approve bg-approve text-white"
              : "border-rule bg-white text-charcoal hover:border-approve hover:text-approve",
          )}
        >
          <svg width="14" height="14" viewBox="0 0 12 12" aria-hidden="true">
            <path d="M2 6.5L4.8 9L10 3" fill="none" stroke="currentColor" strokeWidth="1.6" />
          </svg>
          {decision === "approved" ? "Approved" : "Approve"}
        </button>
        <button
          type="button"
          aria-pressed={decision === "rejected"}
          aria-label={`Reject ${m.units} of ${m.sku_id} from ${m.from} to ${m.to}`}
          onClick={() => onDecide(m.id, "rejected")}
          className={cn(
            "inline-flex h-11 flex-1 items-center justify-center gap-1.5 rounded-lg border px-2.5 text-[13px] font-medium transition-[background-color,border-color,color,transform] duration-150 active:scale-[0.97]",
            `min-[1100px]:h-8 min-[1100px]:flex-none`,
            FOCUS,
            decision === "rejected"
              ? "border-oxblood bg-oxblood text-white"
              : "border-rule bg-white text-charcoal hover:border-oxblood hover:text-oxblood",
          )}
        >
          <svg width="14" height="14" viewBox="0 0 12 12" aria-hidden="true">
            <path d="M3 3L9 9M9 3L3 9" fill="none" stroke="currentColor" strokeWidth="1.6" />
          </svg>
          {decision === "rejected" ? "Rejected" : "Reject"}
        </button>
      </div>

      {expanded && (
        <dl
          id={detailsId}
          className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-lg bg-ivory p-3 text-xs tabular-nums [grid-area:details] sm:grid-cols-4 [&_dd]:font-semibold [&_dd]:text-charcoal [&_dt]:text-stone"
        >
          <div>
            <dt>Sells per day</dt>
            <dd>{m.numbers.velocity.toFixed(2)}</dd>
          </div>
          <div>
            <dt>Days in stock (of 84)</dt>
            <dd>{m.numbers.days_in_stock_84}</dd>
          </div>
          <div>
            <dt>{m.type === "pull_back" ? "Source cover before → after" : "Cover before → after"}</dt>
            <dd>
              {fmtCover(m.numbers.cover_before)} → {fmtCover(m.numbers.cover_after)}
            </dd>
          </div>
          <div>
            <dt>Season lift</dt>
            <dd>×{m.numbers.lift.toFixed(2)}</dd>
          </div>
          <div>
            <dt>Lead time</dt>
            <dd>{m.lead_days} days</dd>
          </div>
          <div>
            <dt>Arrives</dt>
            <dd>{formatDate(m.arrives_on)}</dd>
          </div>
        </dl>
      )}
    </li>
  );
});
