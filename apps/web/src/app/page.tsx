import { DataIssues } from "@/components/approve/DataIssues";
import { HowItWorks } from "@/components/approve/HowItWorks";
import { RunConsole } from "@/components/approve/RunConsole";
import { RunError } from "@/components/approve/RunError";
import { SiteHeader } from "@/components/approve/SiteHeader";
import { StoreHealthStrip } from "@/components/approve/StoreHealthStrip";
import { BadgeStrip, FeatureGrid, FinalCta, Hero, QuoteBanner, SectionHead, SiteFooter } from "@/components/landing/Programa";
import { formatCompactINR, formatDate, formatIST, formatNum, triggerPhrase } from "@/lib/format";
import { loadRun, type Move } from "@/lib/run";

export default async function Home() {
  const result = await loadRun();

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

  const counts: Record<Move["type"], number> = { warehouse_to_store: 0, store_to_store: 0, pull_back: 0 };
  let units = 0;
  let value = 0;
  let senior = 0;
  for (const m of moves) {
    counts[m.type] += 1;
    units += m.units;
    value += m.value_mrp;
    if (m.needs_senior_approval) senior += 1;
  }

  const stats = [
    { value: formatNum(moves.length), label: "moves today" },
    { value: formatNum(units), label: "units", shape: "sq" as const },
    { value: String(run.stores.length || 20), label: "stores" },
    { value: formatCompactINR(value), label: "at MRP", shape: "sq" as const },
    { value: ruleCount ? `${rulesPassed}/${ruleCount}` : "–", label: "rules passed", shape: "dia" as const },
    { value: String(senior), label: "senior approvals" },
    { value: String(run.data_issues.length), label: "data issues", shape: "sq" as const },
    { value: formatNum(counts.store_to_store), label: "store to store", shape: "dia" as const },
  ];

  return (
    <>
      <SiteHeader />
      <main>
        <Hero topMove={topMove} moveCount={moves.length} dataAsOf={formatDate(run.run.data_as_of, true)} />
        <BadgeStrip stats={stats} />
        <FeatureGrid counts={counts} rules={{ passed: rulesPassed, total: ruleCount }} />
        <QuoteBanner />

        <SectionHead
          id="run-title"
          title="Today’s run"
          body={`${formatNum(moves.length)} moves, ${formatNum(units)} units worth ${formatCompactINR(value)} at MRP. Approve, reject, then export.`}
        />
        <div className="mt-10">
          <StoreHealthStrip stores={run.stores} />
        </div>
        <section
          id="run"
          tabIndex={-1}
          aria-label="Today's run"
          className="mx-auto w-full max-w-[1200px] scroll-mt-4 px-4 outline-none md:px-6"
        >
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
        <FinalCta />
      </main>
      <SiteFooter />
    </>
  );
}
