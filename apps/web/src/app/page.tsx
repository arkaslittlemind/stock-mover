import { DataIssues } from "@/components/approve/DataIssues";
import { HeroTicket } from "@/components/approve/HeroTicket";
import { HowItWorks } from "@/components/approve/HowItWorks";
import { RunConsole } from "@/components/approve/RunConsole";
import { RunError } from "@/components/approve/RunError";
import { SiteHeader } from "@/components/approve/SiteHeader";
import { StoreHealthStrip } from "@/components/approve/StoreHealthStrip";
import { formatDate, formatIST, formatNum, triggerPhrase } from "@/lib/format";
import { loadRun, type Move } from "@/lib/run";

export default function Home() {
  const result = loadRun();

  if (!result.ok) {
    return (
      <>
        <SiteHeader showJump={false} />
        <RunError problem={result.problem} paths={result.paths} />
      </>
    );
  }

  const { run } = result;
  const moves = [...run.moves].sort((a, b) => b.priority - a.priority);
  const topMove: Move | null = moves[0] ?? null;
  const rulesPassed = run.rule_check.filter((r) => r.passed).length;
  const ruleCount = run.rule_check.length;
  const runInfo = `Data as of ${formatDate(run.run.data_as_of, true)} close, generated ${formatIST(run.run.generated_at)} ${triggerPhrase(run.run.trigger)}.`;

  return (
    <>
      <SiteHeader />
      <main className="pb-24">
        <section className="mx-auto grid w-full max-w-[1240px] items-center gap-8 px-4 pt-8 pb-14 md:grid-cols-[minmax(0,1fr)_minmax(0,520px)] md:gap-14 md:px-8 md:pt-14 md:pb-20">
          <div>
            <h1 className="font-serif text-[42px] leading-[1.02] tracking-[-0.02em] text-balance md:text-[clamp(42px,5.2vw,68px)]">
              The right stock in the <em className="text-oxblood">right store.</em>
            </h1>
            <p className="mt-5 max-w-[44ch] text-[15px] text-stone md:text-base">
              Every morning Stock Mover plans warehouse, store-to-store and pull-back moves for 20 stores, checks each
              against the merchandising rules, and hands you a list to approve.
            </p>
            <div className="mt-7 flex flex-wrap items-center gap-4">
              <a
                href="#run"
                className="inline-flex h-11 items-center rounded-lg bg-oxblood px-5 font-semibold text-ivory transition-[background-color,transform] duration-150 ease-out-strong hover:bg-oxblood-deep focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-saffron active:scale-[0.97]"
              >
                Review today’s moves
              </a>
              <span className="text-[13px] text-stone tabular-nums">
                {formatNum(moves.length)} moves waiting · data as of {formatDate(run.run.data_as_of)}
              </span>
            </div>
            <p className={`mt-4 text-[13px] font-medium tabular-nums ${ruleCount === 0 ? "text-stone" : rulesPassed === ruleCount ? "text-approve" : "text-oxblood"}`}>
              {ruleCount ? `Rule check: ${rulesPassed} of ${ruleCount} rules passed` : "Rule check unavailable"}
            </p>
            <p className="mt-6 text-xs text-stone md:mt-10">Built for the Manyavar Stock Mover challenge</p>
          </div>
          <HeroTicket move={topMove} />
        </section>

        <StoreHealthStrip stores={run.stores} />
        <section id="run" tabIndex={-1} aria-label="Today's run" className="mx-auto w-full max-w-[1240px] scroll-mt-4 px-4 outline-none md:px-8">
          <RunConsole
            runId={run.run.id}
            dataAsOf={run.run.data_as_of}
            runInfo={runInfo}
            briefing={run.briefing}
            moves={moves}
            dataIssueCount={run.data_issues.length}
          />
        </section>

        <DataIssues issues={run.data_issues} />
        <HowItWorks />
      </main>
    </>
  );
}
