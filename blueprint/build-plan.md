# Build Plan (hackathon day, 21 Nov 2026)

One day, solo: a merchandiser opens a public URL and sees today's
ready-to-approve stock list, with a reason for every move, a rule check that
shows no rule broken, and a briefing, produced by a daily run nobody triggers.
Build the engine core first, put a list on the live URL early, then deepen the
engine, then add the briefing and the daily run.

Each item is one Blueprint feature (`/feature → /implement → /check →
/complete`), then **push** (Blueprint never pushes). Done-whens are written so
`/check` can prove them. Items marked **[audit]** get `/audit current` only if
on schedule. Hard stops come from `../MEMORY.md`: feature freeze 3:45 pm, video
by 4:15, submit by 4:30, last push before 4:45 pm.

## Setup (11:35 to 12:00, not a Blueprint feature)

- Monorepo folders `engine/`, `apps/web/`, `data/raw/`. Copy the 17 CSVs into
  `data/raw/`. `uv init` the engine (Python 3.12, pandas, pydantic, pytest).
  `pnpm create next-app` in `apps/web` (TypeScript, Tailwind, App Router), add
  shadcn/ui and Zod. `.env.example` with `SARVAM_API_KEY`,
  `BLOB_READ_WRITE_TOKEN`, `SARVAM_MODEL`. Commit and push.
- Deploy the Next.js shell to Vercel (Root Directory `apps/web`) so the live URL
  works. Record the URL in `../MEMORY.md`.
- Install Blueprint (`npx create-ai-blueprint@latest --codex --claude`), add the
  `../MEMORY.md` pointer line at the top of `AGENTS.md`, copy these two plans into
  `blueprint/`, `/onboard`, `/overview`. Commit and push.

## Items

- [x] 1. **Loader, data checks, output contract** (12:00 to 12:30) - load all
  CSVs as text with typed conversions; drop packaging; treat missing snapshot
  rows as 0; data checks for negative stock and snapshot vs last weekly close;
  join checks; Pydantic models for the output contract (project plan §5) and a
  JSON Schema export for the web app. *Done when:* tests show KNP-03 SHW-02-L
  and MYS-02 KUR-02-M flagged as data issues with plain-words notes and
  excluded, no other location-SKU flagged, and a sample run JSON validates
  against the schema.
- [x] 2. **Velocity, season lift, cover** (12:30 to 1:00) - per-day-in-stock
  velocity over 84 days; peer velocity for low days in stock, new stores and new
  styles; per-zone season lift (capped 1.0 to 3.0); forecast and cover per
  store-SKU and per style. *Done when:* fixture tests prove stock-out masking is
  removed (a SKU in stock 14 of 84 days gets a per-day rate, not a per-84-day
  rate); BLR-05 uses peer velocity; LKO-01 KUR-04 shows a high forecast; and a
  hand-computed velocity for 3 real store-SKUs matches the engine.
- *Lunch 1:00 to 1:15. Switching statement closes at 1:00 (not switching).*
- [x] 3. **Warehouse → store + seed run** (1:15 to 1:45) - targets (lead time
  + 30 days, min display floor), needs net of in-transit, one-unit-at-a-time
  fair-share allocation by lowest projected cover, capacity headroom, Rs
  1,00,000 approval tag, priority, template reasons; CLI `uv run stock-mover
  run` writes `out/latest.json`; copy it to `apps/web/data/seed-run.json`.
  *Done when:* tests prove allocation never exceeds warehouse stock or store
  capacity and never resends in-transit stock; KUR-01's 50 warehouse units go to
  the stores with the lowest cover; MZF-01 and BLR-05 get min-display top-ups;
  LKO-01 gets KUR-04.
- [x] 4. **Approve page on the live URL** (1:45 to 2:20) - Next.js page reading
  the seed run through Zod: briefing slot, grouped moves with one-line reasons
  and expandable numbers, approve or reject per move and per group
  (localStorage), Needs senior approval tag, filters (area manager or city, type,
  category), Export approved CSV, data issues panel, run info. Run `/prototype`
  first only if it fits in 10 minutes. *Done when:* the deployed URL shows the
  list from the seed run with no sign-in; approvals survive a reload; the export
  CSV has exactly the approved moves; an invalid run file shows an error state
  instead of crashing; no horizontal scroll at 390 px.
- [x] 5. **Store → store, ageing, pull back, rule validator** [audit] (2:20 to
  2:55) - donor selection (30 days of style cover kept, min display kept, S++
  protected styles never given, nearest lead time first); ageing moves (over 180
  days old and over 120 days of cover) to the fastest-selling store with
  headroom, else pull back to WH-KOL; over-capacity pull backs; independent rule
  validator over the final list, published in the run; store health and
  under-stocked flags. Regenerate the seed run and push. *Done when:* tests
  prove each rule is enforced by the validator (one failing fixture per rule);
  the real run reports 0 broken rules; JKT-08 and IW-08 appear in ageing moves;
  no protected style leaves an S++ store; the live page shows all three groups,
  the rule check badge and the store health strip.
- [ ] 6. **LLM briefing with number check** (2:55 to 3:20) - Sarvam chat call
  from the engine with a facts JSON; number checker (every number in the text
  must appear in the facts); one retry, then template fallback; `briefing.source`
  and `checked` in the run; key from env only. Test the key works before
  building (a 1-line call). *Done when:* a test with a fake LLM proves a text
  with an invented number is rejected and the template is used; a real run
  produces a checked LLM briefing; the page shows it with an "AI-written,
  numbers checked" note.
- [ ] 7. **Runs on its own: daily job** (3:20 to 3:45) - GitHub Actions
  workflow (daily cron 06:00 IST plus manual dispatch): uv install, engine run,
  briefing, upload `latest.json` to Vercel Blob; **no git commit in the job**;
  the web app reads the latest Blob run (short revalidate) with the seed run as
  fallback; run info shows the trigger and time. Secrets set by the user in
  GitHub and Vercel. *Done when:* a manual dispatch succeeds, the live page
  shows that run's `generated_at`, and the workflow file has no `git push` or
  commit step.
- **3:45 feature freeze.** Only main-flow bug fixes after this.

## After freeze (not Blueprint features)

| Time | Task |
|---|---|
| 3:45 to 4:00 | README: problem, user, live link, video link, how it works (velocity, fair share, rule validator, briefing), how to run locally, stack, AI tools and models used, the hidden problems found |
| 4:00 to 4:15 | 2-minute video of the live build (briefing → KUR-04 at LKO-01 → KUR-01 fair share → a store-to-store move → data issues → rule check → export) |
| By 4:30 | Submit on the live page: repo, live link, video, one line on what it does |
| Before 4:45 | Last push. Nothing after 4:45 |

## Cut order if behind

1. Drop `/audit` and `/prototype`.
2. Item 7 falls back to a workflow that runs the engine and uploads, without the
   briefing step.
3. Item 6 ships as the template briefing only.
4. Item 5 keeps the validator and store → store; ageing becomes pull back only.

Never cut: the rule validator, the data-issue exclusions, and the live URL
working on first open.

## Split between models (from `../MEMORY.md`)

**Claude is the primary driver for every item** (Opus 5.5 for planning and
hard bugs, Sonnet 5.5 by default): `/feature`, `/implement`, `/check`,
`/complete`, push.

**Codex (GPT Sol) runs background audits and checks, read-only.** After Claude's
`/implement` on an item, Codex runs `$audit current` (or reviews the diff) in its
own session and reports findings; it does not edit files while Claude is
working, so the two never write the same files. Claude applies the fixes. The
done-whens are still proved by Claude's `/check`.

**Fallback:** if Claude's limits run low (check `/usage` at about 1 pm and
2:30 pm), Codex takes over the current feature with `$implement` from
`current-feature.md`, and hands back when Claude is available.

## LLM budget (Sarvam event credits)

| Use | Calls | Note |
|---|---|---|
| Key check and development | about 20 | Small prompts |
| Daily runs and demo dispatches | about 10 | One call per run, at most one retry |
| Page views | 0 | The briefing is precomputed; visitors never trigger a call |
