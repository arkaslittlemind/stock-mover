# Feature: Approve page on the live URL

**From build-plan:** feature 4
**Build attempt:** 1
**Branch:** feature/approve-page-on-the-live-url
**Status:** verified

## Goal

Replace the placeholder home page with the Stock Mover approve page. It uses the
chosen **Dispatch** design, built in Tailwind, and reads the committed seed run
through Zod. A merchandiser can open https://stock-mover.vercel.app with no
sign-in, see today's run, filter it, approve or reject moves one at a time or by
group, keep those decisions across reloads, and export exactly the approved moves
as CSV. An invalid run file shows an error state, not a crash.

## Design reference

- Chosen variant: **Dispatch** from the landing prototype (user decision, 13:05
  IST). Reference code:
  `apps/web/src/app/prototypes/landing/variant-dispatch.tsx` and `dispatch.css`,
  live at `http://localhost:3007/prototypes/landing?v=2` while the prototype exists.
- Changes from the prototype:
  - Bring in two details from the Ledger variant: the headline ends in an italic
    oxblood *"right store."*, and the count numbers use Instrument Serif.
  - Leave out all **Sample** data. Store → Store and Pull back counts come from
    the run (0 in the seed), and the hero shows a rule check only when
    `rule_check` is non-empty.
- Brand: ivory `#FAF6EF`, oxblood `#6E2334`, charcoal `#27211E`, muted saffron
  `#B77A36` used only as an accent, plus green `#3F6B46` for approved.
  Instrument Serif for headlines, Instrument Sans for the interface,
  `tabular-nums` for units and money. The origin-dot-arrow is the recurring
  motif.
- Styling: **Tailwind v4 utilities** (user decision, 13:08 IST). No CSS Modules:
  the Tailwind Turbopack rule in `next.config.ts` breaks them. No inline styles
  (coding standards). A small amount of plain CSS in `globals.css` is allowed only
  for shapes utilities can't express cleanly: the ticket's tear-line notches and
  the dashed stepper line.

## In scope

- **Brand foundation:**
  - Palette tokens in the `globals.css` `@theme` block, so classes like
    `bg-oxblood` and `text-charcoal` exist.
  - Map the existing shadcn variables (`--background`, `--foreground`,
    `--primary`, `--muted`, `--muted-foreground`, `--border`, `--ring`) to the
    palette.
  - Load the fonts with `next/font/google` in `layout.tsx`, replacing Geist,
    exposed as `font-sans` and `font-serif`.
  - Update the page title and description in `layout.tsx`.
- **Run loading:**
  - A server-side loader reads `apps/web/data/seed-run.json`, runs `JSON.parse`,
    then validates with a hand-written Zod schema that matches
    `apps/web/data/run.schema.json` (strict objects and the same enums, minimums,
    nullables and date formats).
  - It returns `{ ok: true, run }` or `{ ok: false, issues }`.
  - Reading from Blob is item 7.
- **Page sections, top to bottom:**
  1. **Slim header:** wordmark on the left, "Review today's moves ↓" jump link on
     the right.
  2. **Hero:**
     - Headline: "The right stock in the *right store.*"
     - One sentence describing the daily recommendations.
     - A **Review today's moves** button that jumps to the run.
     - A note: "<n> moves waiting · data as of <date>".
     - Attribution line: "Built for the Manyavar Stock Mover challenge".
     - A boarding-pass ticket for the **highest-priority move**. It shows the type
       pill, the priority label (Stock-out, Low cover or Top-up, plus Senior
       approval when flagged), large `from` and `to` codes with place names, the
       style and SKU, size, units, value at MRP, arrival date and the one-line
       reason.
     - With no moves, the ticket is replaced by a quiet "No moves today" card.
  3. **Run console (`#run`):** a dark side panel plus a main area.
     - The side panel has:
       - The data date.
       - Type tabs (All, Warehouse → Store, Store → Store, Pull back) with live
         counts.
       - A **City · area manager** select (for example "Lucknow · Rakesh
         Srivastava"; one manager per city in `data/raw/area_managers.csv`).
       - A **Category** select.
       - Totals: units, value at MRP, the senior-approval count and the
         data-issue count.
       - **Export approved CSV (n)** and the run info.
     - The main area has:
       - The morning briefing, with a source label: "Template" or "Written by
         Sarvam AI · numbers checked".
       - Move **groups** by type. Each group header shows the count, units and
         **Approve all shown / Reject all shown**.
       - Rows showing priority, style · SKU · size, the Senior approval tag, the
         reason, route, units, value and Approve and Reject buttons.
       - A **Details** toggle per row that expands the numbers: velocity per
         day, days in stock out of 84, cover before → after, season lift, lead
         days and arrival date.
  4. **Data issues panel:** one entry per `data_issues` item with location, SKU,
     the plain-words note and "Excluded from moves" when `excluded` is true.
  5. **How it works:** three steps: Find stock gaps → Recommend and validate
     moves → Review and export.
- **Run info text:**
  - "Data as of 31 Oct 2026 close, generated <d Mon, h:mm am/pm IST> <by the
    daily run | by a manual run | from the seed run>".
  - The wording is chosen from `run.trigger`: schedule, manual or seed.
- **Long groups:**
  - Each group renders its first 50 filtered rows, then a "Show 50 more" button.
    The page must not mount 810 rows at once.
  - Group approve and reject act on **every filtered move in the group**, not just
    the visible rows, and the button label says the number.
- **Approvals:**
  - Stored in `localStorage` under `stock-mover:approvals:<run.id>` as a JSON
    object of `{ [moveId]: "approved" | "rejected" }`.
  - Pressing the active decision again clears it.
  - Saved approvals are loaded after mount, so server and client HTML match.
  - Storage that is unavailable or holds corrupt JSON gives an empty map without
    crashing. Unknown move ids are ignored.
  - A decision made while storage is unavailable still works for the session.
- **Export:**
  - Covers **all approved moves in the run, ignoring filters**, sorted by
    priority (highest first).
  - Columns: `move_id,type,sku_id,style_name,category,size,from,to,units,value_mrp,arrives_on,needs_senior_approval,reason`.
  - Escaping follows RFC 4180: quote fields containing a comma, quote or line
    break, and double any embedded quotes.
  - File name: `stock-mover-approved-<data_as_of>.csv`.
  - The button is disabled when nothing is approved.
- **States:**
  - **Error:** invalid JSON, a schema mismatch or a missing file shows the header
    plus an error panel: "Today's run could not be read", up to 3 field paths,
    and a note that no moves are shown. It never shows a blank page or a stack
    trace.
  - **Empty run:** zero moves gives "No moves today" in the console and hero.
  - **Empty group:** a type with no moves says, for example, "No store-to-store
    moves in this run."
  - **Filters match nothing:** "No moves match these filters" plus a "Clear
    filters" button.
- **Accessibility and motion:**
  - Every button is reachable by keyboard and has a visible focus ring.
  - Approve and Reject use `aria-pressed`. Details uses `aria-expanded`.
  - The selects have labels. The type tabs are buttons with `aria-pressed`.
  - Jump links scroll smoothly only when reduced motion is off.
  - The ticket's entrance animation uses `motion-safe:`.
- **Responsive:**
  - No horizontal page scroll at 390 px.
  - On mobile the hero copy sits above the ticket, the console stacks with the
    side panel on top and the type tabs wrap, and rows stack.
  - Route and units stay large on mobile, and Approve and Reject are at least
    44 px tall.
- **Cleanup:**
  - Delete `apps/web/src/app/prototypes/` once the page is built.
  - Delete the screenshots in `stock-mover/.playwright-mcp/` and add
    `.playwright-mcp/` to `.gitignore`.

## Out of scope

- Rule check badge, store health strip and real store-to-store and pull-back moves
  (item 5). The page must handle a non-empty `rule_check` safely (shown as a
  simple summary) but item 5 designs it.
- Sarvam briefing (item 6). Only the source label switches on `briefing.source`.
- Reading the run from Vercel Blob, and the daily job (item 7).
- Engine changes, including the template briefing's "Rs 1,13,93,257" and "2193"
  formatting. Note it for item 6, which rewrites the briefing.
- A web unit-test runner (needs `/tests`), dark mode, sign-in.
- `stock-mover-visual-prototype-prompt.md` (untracked, Codex's file): leave it alone.

## Build loop

`workflow.stepReview` is `feature`: build all steps, then present the whole diff
for one review. `workflow.checkpointCommits` is `disabled`: no commits during
implement. `/complete` makes the single feature commit, merges to `main` and
pushes, which deploys. Run `pnpm exec tsc --noEmit` and `pnpm lint` in `apps/web`
after each step, and `pnpm build` at the end.

## Build steps

- [x] **1. Brand foundation, run loader, hero and error state.**
  - Add the tokens and shadcn variable mapping in `globals.css`, the fonts and
    metadata in `layout.tsx`, the Zod schema and `loadRun()` in `src/lib/run.ts`,
    the store, city and area-manager lookup in `src/lib/stores.ts`, and the
    formatters in `src/lib/format.ts`.
  - Rewrite `src/app/page.tsx` to render the header, hero and ticket from the top
    move, or the error panel when the loader fails.
  - *Done when:* `/` in the dev server shows the Dispatch header and hero with the
    LKO-01 KUR-04-XL ticket (45 units, ₹3,23,955, arrives 4 Nov) in Instrument
    Serif and Instrument Sans. With a deliberately broken local copy of
    `seed-run.json` (invalid JSON, then a bad field such as `units: 0`), `/`
    shows the error panel with the field path instead of crashing. Restore the
    file with `git checkout -- apps/web/data/seed-run.json` afterwards. tsc and
    lint pass.
- [x] **2. Run console: filters, groups, rows, details.**
  - Build the client `RunConsole` with the side panel, briefing, run info, type,
    city and category filters, grouped rows with "Show 50 more", the Details
    toggle and every empty state.
  - *Done when:*
    - All shows 810 moves and Warehouse → Store shows 810.
    - Store → Store and Pull back show 0 with their empty-group message.
    - "Lucknow · Rakesh Srivastava" narrows the list to LKO-* destinations and the
      counts update.
    - A category plus city combination that matches nothing shows "No moves
      match these filters", and Clear filters restores all 810.
    - "Show 50 more" adds rows.
    - Details expands the numbers for a row.
    - At 390 px, `document.documentElement.scrollWidth` equals `clientWidth`.
    - tsc and lint pass.
- [x] **3. Decisions, export, data issues, how it works, cleanup.**
  - Add per-move and per-group approve and reject saved to `localStorage`, the
    CSV export, the data issues panel and the How it works section.
  - Delete the prototype surface and screenshots, and add the `.gitignore` entry.
  - *Done when:*
    - After approving 3 moves, rejecting 1 and reloading, the same 4 decisions
      are still shown.
    - Approve all shown on a city-filtered group approves exactly that group's
      filtered count.
    - The downloaded CSV has a header plus exactly one row per approved move with
      matching `move_id`s, and the comma-containing `reason` fields are quoted.
    - The data issues panel lists KNP-03 SHW-02-L and MYS-02 KUR-02-M.
    - Keyboard Tab reaches Approve, Reject, Details and Export, with visible
      focus.
    - `pnpm build` succeeds.
    - `pnpm start` serves `/` with no console errors.
    - No horizontal scroll at 390 px.
    - `apps/web/src/app/prototypes/` no longer exists.

## Files / areas

- `apps/web/src/app/globals.css`: palette tokens, shadcn variable mapping, the
  two small shape rules.
- `apps/web/src/app/layout.tsx`: Instrument fonts, metadata.
- `apps/web/src/app/page.tsx`: server component that calls `loadRun()` and
  renders the sections or the error panel.
- `apps/web/src/lib/run.ts`: Zod schema, `Run`/`Move` types, `loadRun()`
  (server only).
- `apps/web/src/lib/stores.ts`: `STORES` lookup (store id → city, tier, area
  manager), copied from `data/raw/stores.csv` and `area_managers.csv`, plus
  `WH-KOL` → "Kolkata warehouse". An unknown id falls back to the raw id.
- `apps/web/src/lib/format.ts`: Indian rupee and number formatting, dates, IST
  time, priority label.
- `apps/web/src/lib/approvals.ts`: storage key, safe load and save,
  `toApprovedCsv()` (pure).
- `apps/web/src/components/approve/`: `SiteHeader.tsx`, `HeroTicket.tsx`,
  `RouteArrow.tsx`, `RunConsole.tsx` (client), `MoveRow.tsx`, `DataIssues.tsx`,
  `HowItWorks.tsx`, `RunError.tsx`.
- Delete: `apps/web/src/app/prototypes/`, `stock-mover/.playwright-mcp/`. Edit:
  `stock-mover/.gitignore`.

## Data / contracts

- The run contract is locked (item 1). The Zod schema mirrors
  `apps/web/data/run.schema.json` and must not loosen it: strict objects; `units`
  ≥ 1; `value_mrp` and `lead_days` ≥ 0; `days_in_stock_84` between 0 and 84;
  `cover_before` and `cover_after` are a number or null; dates are `YYYY-MM-DD`;
  `generated_at` is an ISO datetime; the type, source and checks enums match.
- Approvals are browser-only (overview). The key is
  `stock-mover:approvals:<run.id>`, and the value is a JSON object mapping move id
  to `"approved"` or `"rejected"`. Nothing is sent to a server.
- The CSV columns and escaping are defined in In scope. They are a user-facing
  download, not an API.
- All text in the run (reasons, notes, briefing) renders as React text nodes.
  Never use `dangerouslySetInnerHTML`.
- The run file is trusted committed data, but it is still validated (coding
  standards).

## Testing

- The web app has no unit test runner (`AGENTS.md`: verify with build, lint,
  typecheck and browser evidence), so this feature adds no unit tests and does not
  install a runner. CSV escaping and storage parsing are proven with browser
  evidence: a downloaded file, and a reload after deliberately corrupting the
  storage value in DevTools.
- The engine suite must stay green (`cd engine && uv run pytest -q`: 81 passed
  before this feature). No engine files change.
- Browser evidence for each step's done-when: the dev server plus Playwright MCP
  screenshots at 1440 px and 390 px, and the console log.
- Live-URL evidence (no sign-in, list visible) is gathered after `/complete`
  pushes to `main`. `/check` uses a local production build (`pnpm build && pnpm
  start`).

## Notes for the AI

- Next.js 16 has breaking changes. Read the relevant guides in
  `apps/web/node_modules/next/dist/docs/` before writing the loader.
  `cacheComponents: true` is on, so confirm how a server component reading a file
  with `fs` must be written (for example `"use cache"`, or reading at build time)
  so that `pnpm build` passes and the page stays static.
- Resolve the seed path from `process.cwd()` (the Vercel Root Directory is
  `apps/web`). Make sure the file is in the deployment: a static render at build
  time is enough. If not, use output file tracing.
- Pass the client console only what it needs. The full 810-move list (~600 KB as
  JSON) is acceptable today, but don't pass the raw parse result twice.
- Priority label rule (from the prototype): `cover_before === 0` → Stock-out;
  `< 7` → Low cover; otherwise Top-up. Store-to-store → Rebalance. Pull back →
  Ageing.
- Use `motion-safe:` for the ticket entrance (opacity and translate only, under
  300 ms, ease-out). Leave the rest static.
- Tailwind v4: tokens go in `@theme` (`--color-oxblood: #6E2334;` and so on), and
  font variables from `next/font` map to `--font-sans` and `--font-serif`. Watch
  the existing `--font-sans: var(--font-sans)` self-reference in `@theme inline`:
  rename the `next/font` variables to avoid a cycle.
- Reuse the prototype's copy and layout decisions. Do not import from
  `prototypes/`. Port the code, then delete the folder.

## Verification (implement, 21 Nov)

- `pnpm exec tsc --noEmit` and `pnpm lint` pass. `pnpm build` passes and `/` is prerendered static.
- Engine: `uv run pytest -q` gives 81 passed (no engine files changed).
- Browser (production server, Playwright MCP):
  - Tabs read All 810 / W→S 810 / S→S 0 / Pull back 0, and the empty-group messages show.
  - Lucknow · Rakesh Srivastava narrows the list to 206 moves, all to LKO-*. Lucknow + Sherwani gives "No moves match", and Clear restores 810.
  - Show more takes the list from 50 to 100. Details expands the numbers.
  - Approve 3 + reject 1 survive a reload, and storage holds exactly those 4.
  - The CSV has 3 rows matching the approved ids, and its reasons are quoted.
  - Approve all on Mysuru approves 52 moves (55 approved in total).
  - Corrupt storage loads 0 decisions without a crash, and Export is disabled.
  - At 390 px, scrollWidth equals clientWidth and Approve is 44 px tall.
  - The focus ring shows (saffron outline). There are 0 console errors or warnings.
- Error state: building with invalid JSON shows "Today’s run could not be read / not valid JSON". Building with `units: 0` shows "moves.0.units: Too small". The seed was restored with `git checkout`.
- Implementation notes:
  - The route column is 160 px and does not wrap (`WH-KOL` was breaking at the hyphen).
  - Group buttons read "Approve all N" / "Reject all N", acting on the filtered group.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":17901,"specSha256":"f8792f2c83c0667a357cc6065001a095af75dd0eb5330e4cf6046df7bc68926f","branch":"refs/heads/feature/approve-page-on-the-live-url","head":"1014b3383bdf715821c1b0aa5291b2839401963b","baseRef":"refs/heads/main","baseCommit":"1014b3383bdf715821c1b0aa5291b2839401963b","sourceTree":"e121ad181dd0dd747894e8e46469f51b830b2b46","landing":"local-merge","absentOptional":[]} -->

## Try it now

1. In `apps/web`, run `pnpm dev`, then open http://localhost:3000 (or the live URL https://stock-mover.vercel.app after the push deploys).
2. Click **Review today’s moves**, approve the first move (LKO-01 KUR-04-XL), then reload. It still shows **Approved**, and the side panel reads “Export approved CSV (1)”.
3. Click Export. It downloads `stock-mover-approved-2026-10-31.csv` with the header row plus one row for `w2s-LKO-01-KUR-04-XL`.
