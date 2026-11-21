"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { loadDecisions, saveDecisions, toApprovedCsv, type Decision, type Decisions } from "@/lib/approvals";
import { formatCompactINR, formatDate, formatNum, MOVE_TYPES, TYPE_EMPTY, TYPE_LABEL } from "@/lib/format";
import type { Move, MoveType } from "@/lib/run";
import { areaManagerFor, CITIES, storeCity } from "@/lib/stores";
import { cn } from "@/lib/utils";
import { FOCUS, MoveRow } from "./MoveRow";

const PAGE = 50;

type TypeFilter = "all" | MoveType;

type Props = {
  runId: string;
  dataAsOf: string;
  runInfo: string;
  briefing: { text: string; source: "llm" | "template"; checked: boolean };
  moves: Move[];
  dataIssueCount: number;
};

/** The store a move belongs to for the city filter: the destination, or the source for a pull back. */
const moveCity = (m: Move) => storeCity(m.type === "pull_back" ? m.from : m.to);

export function RunConsole({ runId, dataAsOf, runInfo, briefing, moves, dataIssueCount }: Props) {
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("all");
  const [city, setCity] = useState("");
  const [category, setCategory] = useState("");
  const [shown, setShown] = useState<Record<MoveType, number>>({
    warehouse_to_store: PAGE,
    store_to_store: PAGE,
    pull_back: PAGE,
  });
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(new Set());
  const [decisions, setDecisions] = useState<Decisions>({});
  const [loaded, setLoaded] = useState(false);
  const [storageOk, setStorageOk] = useState(true);

  const moveIds = useMemo(() => new Set(moves.map((m) => m.id)), [moves]);
  const categories = useMemo(() => [...new Set(moves.map((m) => m.category))].sort(), [moves]);

  // Saved decisions load after mount so server and client HTML match.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time read of browser storage on mount
    setDecisions(loadDecisions(runId, moveIds));
    setLoaded(true);
  }, [runId, moveIds]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reflects whether the last save reached storage
    if (loaded) setStorageOk(saveDecisions(runId, decisions));
  }, [decisions, loaded, runId]);

  const decide = useCallback((id: string, d: Decision) => {
    setDecisions((prev) => {
      const next = { ...prev };
      if (next[id] === d) delete next[id];
      else next[id] = d;
      return next;
    });
  }, []);

  const decideMany = useCallback((ids: string[], d: Decision) => {
    setDecisions((prev) => {
      const next = { ...prev };
      for (const id of ids) next[id] = d;
      return next;
    });
  }, []);

  const toggle = useCallback((id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  // City and category narrow everything; the type tabs then pick groups.
  const filtered = useMemo(
    () => moves.filter((m) => (!city || moveCity(m) === city) && (!category || m.category === category)),
    [moves, city, category],
  );
  const byType = useMemo(() => {
    const groups: Record<MoveType, Move[]> = { warehouse_to_store: [], store_to_store: [], pull_back: [] };
    for (const m of filtered) groups[m.type].push(m);
    return groups;
  }, [filtered]);

  const visibleTypes = typeFilter === "all" ? MOVE_TYPES : [typeFilter];
  // A type tab with no moves shows its own empty-group message; only city or category can "match nothing".
  const nothingMatches =
    (city !== "" || category !== "") && moves.length > 0 && visibleTypes.every((t) => byType[t].length === 0);

  const approvedCount = useMemo(() => Object.values(decisions).filter((d) => d === "approved").length, [decisions]);
  const rejectedCount = useMemo(() => Object.values(decisions).filter((d) => d === "rejected").length, [decisions]);
  const totalUnits = useMemo(() => moves.reduce((s, m) => s + m.units, 0), [moves]);
  const totalValue = useMemo(() => moves.reduce((s, m) => s + m.value_mrp, 0), [moves]);
  const seniorCount = useMemo(() => moves.filter((m) => m.needs_senior_approval).length, [moves]);

  function clearFilters() {
    setTypeFilter("all");
    setCity("");
    setCategory("");
  }

  function exportCsv() {
    const blob = new Blob([toApprovedCsv(moves, decisions)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `stock-mover-approved-${dataAsOf}.csv`;
    document.body.append(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  const tabs: { key: TypeFilter; label: string; count: number }[] = [
    { key: "all", label: "All moves", count: filtered.length },
    ...MOVE_TYPES.map((t) => ({ key: t, label: TYPE_LABEL[t], count: byType[t].length })),
  ];

  const selectClass = cn(
    "mt-1 h-9 w-full rounded-lg border border-ivory/15 bg-ivory/6 px-2.5 text-[13px] text-ivory [&>option]:text-charcoal",
    FOCUS,
  );

  return (
    <div className="grid overflow-hidden rounded-xl bg-white shadow-[0_0_0_1px_rgba(39,33,30,0.1),0_32px_64px_-40px_rgba(39,33,30,0.4)] md:grid-cols-[260px_minmax(0,1fr)] md:rounded-2xl">
      <aside className="min-w-0 bg-charcoal px-3 py-[18px] text-ivory md:px-4 md:py-[22px]">
        <h2 className="px-2 font-serif text-[26px] leading-[1.1]">Today’s run</h2>
        <p className="mt-1 px-2 text-xs text-ivory/60">Data as of {formatDate(dataAsOf, true)}</p>

        <div className="mt-5 flex flex-wrap gap-1.5 md:flex-col md:gap-0.5" role="group" aria-label="Move type">
          {tabs.map((t) => (
            <button
              key={t.key}
              type="button"
              aria-pressed={typeFilter === t.key}
              onClick={() => setTypeFilter(t.key)}
              className={cn(
                "flex h-[34px] items-center justify-between gap-2 rounded-lg px-2.5 text-left text-[13px] transition-colors duration-150 md:h-[38px]",
                "bg-ivory/6 text-ivory/72 hover:text-white md:bg-transparent",
                "aria-pressed:bg-ivory/12 aria-pressed:text-white md:aria-pressed:bg-ivory/10",
                FOCUS,
              )}
            >
              <span>{t.label}</span>
              <b className="font-semibold tabular-nums">{formatNum(t.count)}</b>
            </button>
          ))}
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2 px-0 md:grid-cols-1 md:px-2">
          <label className="block text-[11px] font-medium tracking-[0.06em] text-ivory/60 uppercase">
            City · area manager
            <select value={city} onChange={(e) => setCity(e.target.value)} className={selectClass}>
              <option value="">All cities</option>
              {CITIES.map((c) => (
                <option key={c} value={c}>
                  {c} · {areaManagerFor(c)}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-[11px] font-medium tracking-[0.06em] text-ivory/60 uppercase">
            Category
            <select value={category} onChange={(e) => setCategory(e.target.value)} className={selectClass}>
              <option value="">All categories</option>
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="mt-6 grid grid-cols-2 gap-x-2 gap-y-3.5 border-t border-ivory/12 px-2 pt-[18px] md:grid-cols-1">
          {[
            [formatNum(totalUnits), "units in this run"],
            [formatCompactINR(totalValue), "at MRP"],
            [formatNum(seniorCount), "need senior approval"],
            [formatNum(dataIssueCount), "data issues held back"],
          ].map(([value, label]) => (
            <div key={label} className="flex flex-col">
              <b className="font-serif text-2xl leading-tight font-normal tabular-nums">{value}</b>
              <span className="text-xs text-ivory/60">{label}</span>
            </div>
          ))}
        </div>

        <div className="mt-6 px-2">
          <button
            type="button"
            onClick={exportCsv}
            disabled={approvedCount === 0}
            className={cn(
              "inline-flex h-10 w-full items-center justify-center rounded-lg bg-ivory text-[13px] font-semibold text-charcoal transition-[opacity,transform] duration-150 active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-40",
              FOCUS,
            )}
          >
            Export approved CSV ({formatNum(approvedCount)})
          </button>
          <p className="mt-2 text-xs text-ivory/60 tabular-nums" aria-live="polite">
            {approvedCount} approved · {rejectedCount} rejected
            {!storageOk && " · saving is off in this browser, decisions last until you close the tab"}
          </p>
          <p className="mt-4 text-xs leading-relaxed text-ivory/50">{runInfo}</p>
        </div>
      </aside>

      <div className="min-w-0">
        <div className="flex flex-col gap-1 border-b border-rule bg-ivory px-4 py-3.5 md:flex-row md:items-baseline md:gap-4 md:px-5 md:py-[18px]">
          <span className="flex-none text-[11px] font-semibold tracking-[0.08em] text-oxblood uppercase">
            Morning briefing
          </span>
          <div>
            <p className="text-sm">{briefing.text}</p>
            <p className="mt-1 text-xs text-stone">
              {briefing.source === "llm"
                ? `Written by Sarvam AI${briefing.checked ? " · numbers checked" : ""}`
                : "Template"}
            </p>
          </div>
        </div>

        {moves.length === 0 ? (
          <p className="px-5 py-16 text-center font-serif text-3xl">No moves today</p>
        ) : nothingMatches ? (
          <div className="px-5 py-16 text-center">
            <p className="font-serif text-2xl">No moves match these filters</p>
            <button
              type="button"
              onClick={clearFilters}
              className={cn("mt-4 h-10 rounded-lg border border-rule px-4 text-sm font-medium hover:border-charcoal", FOCUS)}
            >
              Clear filters
            </button>
          </div>
        ) : (
          visibleTypes.map((t) => {
            const group = byType[t];
            const visible = group.slice(0, shown[t]);
            const ids = group.map((m) => m.id);
            return (
              <section key={t} aria-label={TYPE_LABEL[t]} className="border-b border-rule last:border-b-0">
                <div className="flex flex-wrap items-center justify-between gap-2 bg-[#fcfaf6] px-4 py-3 md:px-5">
                  <h3 className="text-sm font-semibold">
                    {TYPE_LABEL[t]}{" "}
                    <span className="font-normal text-stone tabular-nums">
                      · {formatNum(group.length)} moves · {formatNum(group.reduce((s, m) => s + m.units, 0))} units
                    </span>
                  </h3>
                  {group.length > 0 && (
                    <div className="flex gap-1.5">
                      <button
                        type="button"
                        onClick={() => decideMany(ids, "approved")}
                        className={cn(
                          "h-8 rounded-lg border border-rule bg-white px-2.5 text-xs font-medium hover:border-approve hover:text-approve",
                          FOCUS,
                        )}
                      >
                        Approve all {formatNum(group.length)}
                      </button>
                      <button
                        type="button"
                        onClick={() => decideMany(ids, "rejected")}
                        className={cn(
                          "h-8 rounded-lg border border-rule bg-white px-2.5 text-xs font-medium hover:border-oxblood hover:text-oxblood",
                          FOCUS,
                        )}
                      >
                        Reject all {formatNum(group.length)}
                      </button>
                    </div>
                  )}
                </div>

                {group.length === 0 ? (
                  <p className="px-4 py-6 text-sm text-stone md:px-5">{TYPE_EMPTY[t]}</p>
                ) : (
                  <>
                    <div
                      className="hidden h-9 items-center gap-3.5 border-y border-rule px-5 text-[11px] font-semibold tracking-[0.06em] text-stone uppercase min-[1100px]:grid min-[1100px]:grid-cols-[92px_minmax(0,1fr)_160px_40px_84px_176px]"
                      aria-hidden="true"
                    >
                      <span>Priority</span>
                      <span>Style · size</span>
                      <span>Route</span>
                      <span className="text-right">Units</span>
                      <span className="text-right">Value</span>
                      <span />
                    </div>
                    <ul>
                      {visible.map((m) => (
                        <MoveRow
                          key={m.id}
                          move={m}
                          decision={decisions[m.id]}
                          expanded={expanded.has(m.id)}
                          onDecide={decide}
                          onToggle={toggle}
                        />
                      ))}
                    </ul>
                    <div className="flex items-center justify-between gap-2 px-4 py-3 text-xs text-stone tabular-nums md:px-5">
                      <span>
                        Showing {formatNum(visible.length)} of {formatNum(group.length)}
                      </span>
                      {visible.length < group.length && (
                        <button
                          type="button"
                          onClick={() => setShown((s) => ({ ...s, [t]: s[t] + PAGE }))}
                          className={cn(
                            "h-9 rounded-lg border border-rule px-3 font-medium text-charcoal hover:border-charcoal",
                            FOCUS,
                          )}
                        >
                          Show {Math.min(PAGE, group.length - visible.length)} more
                        </button>
                      )}
                    </div>
                  </>
                )}
              </section>
            );
          })
        )}
      </div>
    </div>
  );
}
