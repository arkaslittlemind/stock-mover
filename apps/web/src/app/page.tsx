export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-4 px-4 py-16">
      <p className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
        Manyavar · Stock Mover
      </p>
      <h1 className="text-3xl font-semibold tracking-tight">
        Today&apos;s stock moves, ready to approve
      </h1>
      <p className="text-muted-foreground">
        A daily engine plans warehouse-to-store, store-to-store and ageing-stock
        moves, checks every move against the merchandising rules, and explains
        each one in a line. The approval list is coming online shortly.
      </p>
    </main>
  );
}
