# Findings

> **Generated file.** The findings ledger: review findings raised by `/audit`
> against the work in progress, each with a durable ID, severity (P0-P3), and
> status. `/implement` marks repaired findings `fixed`, a later `/audit` pass
> moves them to `closed`, and `/complete` refuses to land while any P0 or P1
> finding is `open` or `fixed`, then archives resolved findings with the work
> and resets this file.

### F-01 [P3] open - RunLoadResult.source is set but never read

**File:** apps/web/src/lib/run.ts:104
**Found:** 2026-11-21 by /audit independent (scope: current; lens: quality)
**Why it matters:** `loadRun()` returns `source: "blob" | "seed"`, but no caller reads it; the run info line already distinguishes runs through `run.trigger` and `triggerPhrase`. The unused field and `RunSource` type are dead surface.
**Suggested fix:** Either drop `source` and `RunSource` (no current requirement lost, since `triggerPhrase` already labels seed vs daily vs manual runs) or leave as-is; harmless for the deadline.
**Resolution:**
