const STEPS = [
  {
    title: "Find stock gaps",
    body: "Every morning the engine reads sales, stock and in-transit units and flags each store and size running short or sitting idle.",
  },
  {
    title: "Recommend and validate moves",
    body: "It plans warehouse, store-to-store and pull-back moves, then checks each one against min display, capacity and cover rules.",
  },
  {
    title: "Review and export",
    body: "You approve or reject each move with its one-line reason, then export the approved list for the warehouse and stores.",
  },
];

export function HowItWorks() {
  return (
    <section aria-labelledby="how-title" className="mx-auto w-full max-w-[1200px] px-4 pt-[72px] md:px-6 md:pt-24">
      <h2 id="how-title" className="pg-serif text-[32px] leading-9 tracking-[-0.2px] md:text-[44px] md:leading-[50px]">
        How it works
      </h2>
      <ol className="step-line relative mt-9 grid gap-6 md:grid-cols-3 md:gap-8">
        {STEPS.map((s, i) => (
          <li key={s.title} className="relative pl-12 md:pl-0">
            <span className="absolute top-0 left-0 inline-flex size-8 items-center justify-center rounded-full bg-oxblood text-xs font-semibold text-ivory tabular-nums md:relative">
              0{i + 1}
            </span>
            <h3 className="mt-1 text-[17px] font-semibold md:mt-4">{s.title}</h3>
            <p className="mt-1.5 max-w-[36ch] text-stone">{s.body}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
