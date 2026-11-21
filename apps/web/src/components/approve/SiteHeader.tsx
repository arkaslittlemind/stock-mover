export function SiteHeader({ showJump = true }: { showJump?: boolean }) {
  return (
    <header className="mx-auto flex w-full max-w-[1240px] items-center justify-between px-4 py-3.5 md:px-8 md:py-[18px]">
      <span
        className="inline-flex items-center gap-2 text-xs font-semibold tracking-[0.16em] uppercase md:text-[13px]"
        aria-label="Stock Mover"
      >
        <span className="size-[7px] rounded-full bg-oxblood" aria-hidden="true" />
        <span aria-hidden="true">Stock</span>
        <svg width="26" height="10" viewBox="0 0 26 10" fill="none" className="text-oxblood" aria-hidden="true">
          <path d="M0 5H24" stroke="currentColor" strokeWidth="1.5" />
          <path d="M20 1L24.5 5L20 9" stroke="currentColor" strokeWidth="1.5" />
        </svg>
        <span aria-hidden="true">Mover</span>
      </span>
      {showJump && (
        <a
          href="#run"
          className="inline-flex h-8 items-center gap-1.5 rounded-full border border-rule px-3 text-xs font-medium transition-colors duration-150 hover:border-charcoal focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-saffron md:h-[34px] md:px-3.5 md:text-[13px]"
        >
          Review today’s moves <span aria-hidden="true">↓</span>
        </a>
      )}
    </header>
  );
}
