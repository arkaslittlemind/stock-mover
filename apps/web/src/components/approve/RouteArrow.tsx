import { cn } from "@/lib/utils";

/** The recurring origin → destination motif: a dot, a rule, an arrowhead. Width sets the rule length. */
export function RouteArrow({ width = 56, className }: { width?: number; className?: string }) {
  return (
    <svg
      className={cn("shrink-0", className)}
      width={width}
      height="12"
      viewBox={`0 0 ${width} 12`}
      fill="none"
      aria-hidden="true"
    >
      <circle cx="3" cy="6" r="2.5" fill="currentColor" />
      <path d={`M7 6H${width - 2}`} stroke="currentColor" strokeWidth="1.25" />
      <path d={`M${width - 7} 1.5L${width - 1.5} 6L${width - 7} 10.5`} stroke="currentColor" strokeWidth="1.25" />
    </svg>
  );
}
