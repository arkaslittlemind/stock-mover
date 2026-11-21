import type { ReactNode } from "react";
import { HeroTicket } from "@/components/approve/HeroTicket";
import { LogoMark } from "@/components/approve/SiteHeader";
import { formatNum } from "@/lib/format";
import type { Move } from "@/lib/run";

/** Hero: grid paper, serif headline, the top move shown on a desk monitor. */
export function Hero({ topMove, moveCount, dataAsOf }: { topMove: Move | null; moveCount: number; dataAsOf: string }) {
  return (
    <section className="pg-paper relative overflow-hidden pt-[104px] md:pt-[118px]">
      <div aria-hidden="true" className="hidden md:block">
        <span className="pg-swatch pg-sw-marble" />
        <span className="pg-swatch pg-sw-ribbed" />
        <span className="pg-swatch pg-sw-chikan" />
        <span className="pg-swatch pg-sw-brocade" />
        <span className="pg-swatch pg-sw-check" />
        <span className="pg-swatch pg-sw-peach" />
        <span className="pg-swatch pg-sw-lime" />
      </div>

      <div className="relative z-[2] px-4 text-center">
        <h1 className="pg-serif text-[46px] leading-[44px] tracking-[-1px] font-normal md:text-[80px] md:leading-[72px] md:tracking-[-1.5px]">
          Moved, by morning
        </h1>
        <p className="mx-auto mt-6 max-w-[520px] leading-6 text-stone md:mt-11">
          The calmer way to put every Manyavar piece in the right store. Today’s {formatNum(moveCount)} moves are
          planned, checked against the rules and ready to approve.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2.5">
          <a href="#run" className="pg-btn pg-btn-dark">
            Review today’s moves
          </a>
          <a href="#how-title" className="pg-btn">
            How it works
          </a>
        </div>
        <p className="mt-3 font-mono text-[11px] tracking-[0.04em] text-stone uppercase">Data as of {dataAsOf}</p>
      </div>

      <div className="relative z-[3] mx-auto mt-8 w-full max-w-[600px] px-4 pb-10 md:mt-10 md:px-0">
        <div className="pg-monitor">
          <div className="rounded-[3px] bg-white p-1.5 md:p-4">
            <HeroTicket move={topMove} />
          </div>
        </div>
        <div className="pg-stand" aria-hidden="true" />
        <div className="pg-foot" aria-hidden="true" />
        <div
          aria-hidden="true"
          className="pg-sticky top-[-36px] left-[-150px] hidden h-[124px] w-[136px] rotate-[-3deg] bg-[linear-gradient(170deg,#fff37c,#f8e65a)] text-[32px] lg:block"
        >
          Top move
          <br />
          today :)
        </div>
        <div
          aria-hidden="true"
          className="pg-sticky right-[-150px] bottom-[50px] hidden h-[130px] w-[140px] rotate-[2deg] bg-[linear-gradient(170deg,#ffa9c6,#f78db2)] pt-6 text-[27px] lg:block"
        >
          A run
          <br />
          every
          <br />
          morning
        </div>
      </div>
      <div className="pg-desk" aria-hidden="true" />
    </section>
  );
}

type Stat = { value: string; label: string; shape?: "hex" | "sq" | "dia" };

/** Grey badge marquee with the run's real totals. */
export function BadgeStrip({ stats }: { stats: Stat[] }) {
  const items = [...stats, ...stats];
  return (
    <div
      aria-label="Run totals"
      className="overflow-hidden py-6 [mask-image:linear-gradient(90deg,transparent,#000_8%,#000_92%,transparent)]"
    >
      <ul className="pg-marquee flex w-max gap-14">
        {items.map((s, i) => (
          <li
            key={i}
            aria-hidden={i >= stats.length}
            className={`pg-badge ${s.shape === "sq" ? "pg-badge-sq" : s.shape === "dia" ? "pg-badge-dia" : ""}`}
          >
            <span>
              <span className="block font-mono text-[13px]">{s.value}</span>
              {s.label}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function SectionHead({ title, body, children, id }: { title: string; body: string; children?: ReactNode; id?: string }) {
  return (
    <div className="px-4 pt-14 text-center">
      <h2 id={id} className="pg-serif text-[32px] leading-9 tracking-[-0.2px] md:text-[44px] md:leading-[50px]">
        {title}
      </h2>
      <p className="mx-auto mt-3.5 max-w-[420px] leading-6 text-stone">{body}</p>
      {children && <div className="mt-5 flex justify-center gap-2.5">{children}</div>}
    </div>
  );
}

function FeatureCard({ title, body, children }: { title: string; body: string; children: ReactNode }) {
  return (
    <li className="relative h-[340px] overflow-hidden rounded-[10px] border border-rule bg-paper-card px-5 py-[22px] transition-[box-shadow,transform] duration-200 hover:-translate-y-0.5 hover:shadow-[0_10px_30px_rgba(26,25,22,0.12),0_2px_6px_rgba(26,25,22,0.08)]">
      <h3 className="text-xl leading-7 font-medium">{title}</h3>
      <p className="leading-[22px] text-stone">{body}</p>
      <div className="absolute inset-x-0 top-[118px] bottom-0" aria-hidden="true">
        {children}
      </div>
    </li>
  );
}

const card = "absolute rounded-[10px] border border-[#e2ded6] bg-white shadow-[0_1px_2px_rgba(26,25,22,0.04),0_2px_6px_rgba(26,25,22,0.04)]";
const pill = "flex items-center gap-2 rounded-lg border border-[#e2ded6] bg-white px-3 py-2 text-sm whitespace-nowrap shadow-[0_1px_2px_rgba(26,25,22,0.04)]";

/** Six feature cards with small UI drawings, numbers from the run. */
export function FeatureGrid({ counts, rules }: { counts: Record<Move["type"], number>; rules: { passed: number; total: number } }) {
  return (
    <section id="features" className="mx-auto w-full max-w-[1200px] px-4 md:px-6">
      <SectionHead title="Built by and for merchandisers" body="Every move the network needs today, planned, checked and explained before you open the laptop.">
        <a href="#run" className="pg-btn pg-btn-dark pg-btn-sm">
          Review moves
        </a>
        <a href="#how-title" className="pg-btn pg-btn-sm">
          How it works
        </a>
      </SectionHead>
      <ul className="mt-16 mb-20 grid gap-[22px] md:grid-cols-2 lg:grid-cols-3">
        <FeatureCard title="Warehouse to store" body={`${formatNum(counts.warehouse_to_store)} top-ups from WH-KOL today.`}>
          <div className={`${card} top-6 left-[30%] h-[100px] w-[260px] rotate-[5deg] py-4 pr-4 pl-[100px]`}>
            <span className="absolute top-3.5 left-3.5 size-[72px] rounded-md bg-[linear-gradient(135deg,#efe4cc,#d8c79f)]" />
            <div>LKO-01</div>
            <div className="font-mono text-[13px] text-stone">from WH-KOL</div>
          </div>
          <div className={`${card} top-[92px] left-[22%] h-[140px] w-[290px] rotate-[3deg] pt-[18px] pr-4 pl-[110px]`}>
            <span className="absolute top-4 left-3.5 size-[82px] rounded-md bg-[linear-gradient(135deg,#f3d27a,#d9a441)]" />
            <div>Mustard Yoke Kurta</div>
            <div className="font-mono text-sm text-stone">to PAT-01 · 23 u</div>
            <div className="mt-5 font-mono text-[13px] text-stone">KUR-02-M</div>
          </div>
        </FeatureCard>

        <FeatureCard title="Store to store" body={`${formatNum(counts.store_to_store)} transfers, never stripping a donor.`}>
          <div className={`${card} inset-x-8 top-6 h-[200px] p-4`}>
            <div className={`${pill} justify-between`}>
              ⇄ <span className="flex-1">Balance from donor</span>
              <span className="text-stone">⌄</span>
            </div>
            <div className={`${pill} -mx-2 mt-2 shadow-[0_10px_30px_rgba(26,25,22,0.12)]`}>✦ Keep 30 days of cover at the donor</div>
            <div className="mt-3.5 grid grid-cols-3 gap-2">
              <span className="grid h-[70px] place-items-center rounded-md bg-ivory-deep">
                <span className="size-8 rounded-full bg-[radial-gradient(#e7d6b5_30%,#5a4430_32%)]" />
              </span>
              <span className="grid h-[70px] place-items-center rounded-md bg-ivory-deep">
                <span className="size-8 rounded-full bg-[radial-gradient(#f5e9d4_30%,#6e2334_32%)]" />
              </span>
              <span className="h-[70px] rounded-md bg-ivory-deep" />
            </div>
          </div>
        </FeatureCard>

        <FeatureCard title="Ageing pull-back" body={`${formatNum(counts.pull_back)} slow pieces sent back to reuse elsewhere.`}>
          <div className={`${card} top-3 left-[26%] grid size-[120px] place-items-center bg-paper-card`}>
            <span className="h-[86px] w-14 rounded-[8px_8px_4px_4px] bg-[repeating-linear-gradient(0deg,#2f4a3c_0_6px,#567a65_6px_9px)]" />
          </div>
          <div className={`${card} top-3 left-[62%] grid size-[120px] place-items-center bg-paper-card`}>
            <span className="h-10 w-20 rounded-[50%] bg-[radial-gradient(#d39a5a,#8a5a2c)]" />
          </div>
          <div className={`${card} top-[140px] -left-2.5 grid h-[120px] w-[100px] place-items-center bg-paper-card`}>
            <span className="h-[74px] w-12 rounded-md bg-[#23336b]" />
          </div>
          <div className={`${card} top-[132px] left-[30%] grid h-[130px] w-[120px] -rotate-4 place-items-center bg-paper-card`}>
            <span className="h-7 w-[74px] rounded-[50%] bg-[#e9dfca]" />
          </div>
          <div className={`${card} top-[150px] left-[66%] grid size-[120px] place-items-center bg-paper-card`}>
            <span className="h-[52px] w-16 rounded-[40%] bg-[#f39a2d]" />
          </div>
        </FeatureCard>

        <FeatureCard title="Rule checks" body={`${rules.passed} of ${rules.total} merchandising rules passed.`}>
          {[
            ["Min display per category", "bg-[#5b8def]", "left-6 top-[40px]"],
            ["S++ top-20 protected", "bg-approve", "left-[22%] top-[100px]"],
            ["Store capacity", "bg-[#e7e4de]", "left-6 top-[160px]"],
          ].map(([label, dot, pos]) => (
            <div key={label} className={`absolute ${pos} flex h-[50px] w-[320px] items-center gap-3.5 rounded-xl border border-[#e2ded6] bg-white px-4 text-[18px] whitespace-nowrap shadow-[0_1px_2px_rgba(26,25,22,0.04)]`}>
              <span className={`size-3 rounded ${dot}`} />
              {label}
            </div>
          ))}
          <div className={`${card} -top-2 left-[48%] z-[1] h-[72px] w-[150px] -rotate-6 px-3.5 py-2 font-hand text-2xl leading-[26px] shadow-[0_10px_30px_rgba(26,25,22,0.12)]`}>
            Cover floor
            <br />
            30 days
          </div>
        </FeatureCard>

        <FeatureCard title="Briefing" body="One paragraph. Your morning, in plain words.">
          <div className={`${card} top-6 right-[-20px] left-7 h-[190px] p-5 text-sm leading-[21px]`}>
            <div className="mb-2.5 font-mono text-[11px] text-stone uppercase">Run briefing</div>
            Every move carries a one-line reason: who sells it, how many days of cover the store has, and when it arrives.
            <div className="mt-3.5 flex gap-1.5">
              <span className="rounded-md border border-rule bg-paper-card px-1.5 py-0.5 text-xs text-stone">numbers checked</span>
            </div>
          </div>
        </FeatureCard>

        <FeatureCard title="Approve and export" body="Approve, reject, and download a clean CSV.">
          <div className={`${card} top-4 left-8 h-[200px] w-[240px] bg-[repeating-linear-gradient(90deg,transparent_0_30px,#eee_30px_31px),repeating-linear-gradient(0deg,transparent_0_30px,#eee_30px_31px)]`} />
          <div className={`${card} top-[60px] left-[22%] h-[200px] w-[270px] p-3.5 font-mono text-[11px] leading-[19px] text-stone shadow-[0_10px_30px_rgba(26,25,22,0.12)]`}>
            <div className="text-charcoal">approved.csv</div>
            <div className="mt-3">
              id,from,to,units
              <br />
              w2s-LKO-01-KUR-04-XL,WH-KOL,LKO-01,45
              <br />
              w2s-PAT-01-KUR-02-M,WH-KOL,PAT-01,23
              <br />
              w2s-BLR-02-JKT-01-M,WH-KOL,BLR-02,17
            </div>
          </div>
        </FeatureCard>
      </ul>
    </section>
  );
}

export function QuoteBanner() {
  return (
    <section className="mx-auto w-full max-w-[1200px] px-4 md:px-6">
      <div className="mx-auto grid h-[300px] max-w-[1000px] place-items-center rounded-[14px] bg-black px-8 text-center text-white md:h-[405px]">
        <p className="pg-serif max-w-[620px] text-[30px] leading-9 tracking-[-0.2px] md:text-[44px] md:leading-[50px]">
          “For those of you still moving stock from a spreadsheet, how’s the season going?”
        </p>
      </div>
    </section>
  );
}

export function FinalCta() {
  return (
    <section className="px-4 pt-40 pb-32 text-center md:pt-48 md:pb-40">
      <h2 className="pg-serif mb-8 text-[46px] leading-[44px] tracking-[-1px] md:text-[80px] md:leading-[72px] md:tracking-[-1.5px]">
        Approve today’s run
      </h2>
      <div className="flex justify-center gap-2.5">
        <a href="#run" className="pg-btn pg-btn-cta pg-btn-sm">
          Review moves
        </a>
        <a href="#how-title" className="pg-btn pg-btn-sm">
          How it works
        </a>
      </div>
    </section>
  );
}

export function SiteFooter() {
  const cols: [string, string[]][] = [
    ["Product", ["Warehouse to store", "Store to store", "Ageing pull-back", "Rule checks"]],
    ["Run", ["Today’s moves", "Briefing", "Data issues", "CSV export"]],
    ["Built for", ["Manyavar", "Vibe Coders Hackathon 3", "Calcutta AI Club"]],
  ];
  return (
    <footer className="pg-footer border-t border-rule">
      <div className="mx-auto grid w-full max-w-[1200px] gap-6 px-4 pt-9 pb-10 md:grid-cols-[2fr_1fr_1fr_1fr] md:px-6">
        <span className="inline-flex items-start gap-2 text-2xl">
          <LogoMark className="size-[38px]" />
          Stock Mover
        </span>
        {cols.map(([head, items]) => (
          <div key={head}>
            <h3 className="mb-3 font-mono text-[11px] uppercase">{head}</h3>
            <ul className="space-y-2 text-xs text-stone">
              {items.map((i) => (
                <li key={i}>{i}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="mx-auto w-full max-w-[1200px] border-t border-dashed border-[#e2ded6] px-4 py-3 md:px-6">
        <span className="font-mono text-[11px] text-stone uppercase">© Stock Mover 2026</span>
      </div>
    </footer>
  );
}
