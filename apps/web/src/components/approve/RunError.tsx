export function RunError({ problem, paths }: { problem: string; paths: string[] }) {
  return (
    <main className="mx-auto w-full max-w-[1200px] px-4 pt-28 pb-16 md:px-6">
      <div role="alert" className="max-w-xl rounded-[14px] border border-rule bg-white p-6 md:p-8">
        <p className="text-[11px] font-semibold tracking-[0.08em] text-oxblood uppercase">Run unavailable</p>
        <h1 className="mt-2 font-serif text-4xl leading-tight">Today’s run could not be read</h1>
        <p className="mt-3 text-stone">{problem} No moves are shown, so nothing can be approved from a broken file.</p>
        {paths.length > 0 && (
          <ul className="mt-4 space-y-1 rounded-lg bg-ivory p-3 font-mono text-xs break-words">
            {paths.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        )}
      </div>
    </main>
  );
}
