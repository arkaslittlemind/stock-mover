export function LogoMark({ className = "size-[30px]" }: { className?: string }) {
  return (
    <svg viewBox="0 0 34 34" className={className} aria-hidden="true">
      <circle cx="9" cy="9" r="7" fill="currentColor" />
      <circle cx="9" cy="25" r="7" fill="currentColor" />
      <path d="M18 4h6l8 13-8 13h-6l8-13z" fill="currentColor" />
    </svg>
  );
}

const LINKS = [
  ["Moves", "#run"],
  ["Features", "#features"],
  ["Data issues", "#data-issues-title"],
  ["How it works", "#how-title"],
] as const;

export function SiteHeader({ showJump = true }: { showJump?: boolean }) {
  return (
    <header className="absolute inset-x-0 top-0 z-20 pt-2">
      <div className="mx-auto grid h-14 w-full max-w-[1200px] grid-cols-[auto_1fr] items-center px-4 md:grid-cols-[1fr_auto_1fr] md:px-6">
        <span className="inline-flex items-center gap-2 text-[19px] tracking-[-0.3px] whitespace-nowrap md:text-[21px]">
          <LogoMark />
          Stock Mover
        </span>
        {showJump && (
          <nav aria-label="Sections" className="hidden gap-1.5 md:flex">
            {LINKS.map(([label, href]) => (
              <a key={href} href={href} className="rounded-md px-2.5 py-1.5 text-sm hover:bg-charcoal/5">
                {label}
              </a>
            ))}
          </nav>
        )}
        {showJump && (
          <div className="flex justify-end">
            <a href="#run" className="pg-btn pg-btn-cta h-[30px] px-2.5 text-sm font-medium">
              Review today’s moves
            </a>
          </div>
        )}
      </div>
    </header>
  );
}
