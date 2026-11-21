# Stock Mover — Project Plan (hackathon MVP)

> One-day build for Vibe Coders Hackathon Edition 3 (21 Nov 2026), on Manyavar's
> "Stock Mover" brief (Vedant Fashions Limited, case study B). This file is the
> Blueprint `project-plan.md`: it defines what the product is. The order of work
> is in `build-plan.md`. Hackathon rules, deadlines and the handoff log live in
> `../MEMORY.md` (outside the repo); those win over this file.
>
> The data is synthetic and belongs to Vedant Fashions Limited. No real store,
> salesperson or customer appears in it.

## 1. Problem

Every day, stock sits in the wrong place. A best-selling kurta is out of stock in
the flagship while a small store holds the same style for months. A new style
looks like a flop only because the store that would sell it never got any. A
merchandiser has to work this out by hand across 20 stores, a warehouse and
385 SKUs, under rules about display minimums, capacity and flagship styles.

**Stock Mover** runs every morning on its own. It reads sales and stock, works
out how fast each style and size sells in each store, and produces a
**ready-to-approve list**: what to send from the warehouse, what to move between
stores, and what to pull back. Every move has a one-line reason, and an
independent rule check proves that no move breaks a rule. A merchandiser should
be able to approve the list in ten minutes.

## 2. Users

- **Merchandiser (primary):** opens the list each morning, approves or rejects
  each move, exports the approved list. Wants every move to make sense in one line.
- **Area manager:** filters the list to their city and stores.
- **Judges and Manyavar reviewers:** check that the hidden problems were found,
  spot-check the numbers, and check that no rule is broken and that it runs on
  its own.

## 3. Features (MVP)

### Today's list (single page)
- Morning briefing at the top: 4 to 6 sentences on what matters today, written
  by an LLM from engine numbers only, every number checked (section 5)
- Three groups of moves: **Warehouse → store**, **Store → store**, **Pull back**
  (ageing or excess stock back to the warehouse or to a store that sells it)
- Each move: SKU and style name, from, to, units, value at MRP, lead time and
  arrival date, one-line reason, priority. Expand for the numbers behind it
  (velocity, days in stock, cover before and after, rule checks)
- Approve or reject per move, and "approve all in group"; an **Export approved
  list** CSV
- Moves worth over Rs 1,00,000 at MRP carry a **Needs senior approval** tag (rule)
- Filters: area manager or city, move type, category
- **Rule check badge:** "N moves checked, 0 rules broken", expandable per rule
- **Data issues panel:** numbers that can't be right, flagged and left out of
  the moves (not silently fixed)
- **Store health strip:** each store's fill vs capacity, days of cover, and
  min-display gaps; under-stocked stores highlighted
- Run info: "Data as of 31 Oct 2026 close · generated automatically at <time> by
  the daily run"

### Runs on its own
- A scheduled daily job runs the engine and the briefing, then publishes the
  result. Nobody has to ask it anything
- The site reads the latest published run and falls back to a committed seed
  run, so it works on first open

## 4. Data

Read-only. The 17 CSVs from the Manyavar pack are copied into `data/raw/` and
committed (synthetic, about 15 MB) so the engine runs anywhere without setup.
Profiling notes: `../stock-mover-data-findings.md` (outside the repo).

"Today" is the close of 31 Oct 2026. The snapshot leaves out location-SKU pairs
with zero stock; a missing row is 0. Packaging SKUs (`is_packaging` = 1) are not
products and are left out everywhere. `min_display`'s "Accessories
(Safa/Mala/Stole)" is the sum of three `items` categories. IDs are text.

### Hidden problems the engine must find (from profiling)
1. KNP-03 SHW-02-L shows 300 units in the snapshot; the weekly table shows 0 for
   12 weeks → data issue, excluded
2. MYS-02 KUR-02-M shows -4 units; weekly shows 3 → data issue, excluded
3. KUR-04 (new chikankari kurta) looks slow at LKO-01 only because it was in
   stock 14 of 84 days → masked demand; send it
4. KUR-01 (hero core kurta): 1,748 units sold in 90 days, 28 in stores, 50 at the
   warehouse → not enough for everyone; fair-share allocation
5. MZF-01: best-selling A store, 37% full, about 29 days of cover, below
   Mojari min display → under-stocked
6. BLR-05: opened 10 Oct 2026 → too little history; use peer velocity
7. Dead fashion stock (JKT-08, IW-08, old sherwanis and Indo-Westerns) → pull
   back or consolidate. True slow = no sales with full days in stock
8. Wedding season 20 Nov to 12 Dec, Diwali 8 Nov → plain recent velocity
   understates demand; apply a season lift
9. Sizes S and XXXL overstocked, L and XL short
10. Most stores 77 to 90% full → capacity checks bind

## 5. Engine (Python, deterministic)

All numbers and rule checks are code. The LLM never computes or changes a move.

1. **Load and check.** Load CSVs as text, convert numbers. Data checks: negative
   stock; snapshot on-hand that disagrees with the last `stock_weekly` close;
   SKUs or stores that don't join. Each finding becomes a data issue with a
   plain-words note, and the affected location-SKU is excluded from moves.
2. **Velocity.** For each store and SKU: units sold in the last 84 days ÷ days in
   stock in those 84 days (from `stock_weekly.days_in_stock`). This removes
   stock-out masking. If days in stock is under 14, or the store opened under
   60 days ago, or the style launched under 30 days ago, use **peer velocity**:
   the same SKU's per-day-in-stock velocity in stores of the same tier
   (same zone first, else network), scaled by the store's share of its peers'
   total sales where history exists.
3. **Season lift.** Per zone: last year's daily sales in the 30 days after the
   matching date ÷ last year's daily sales in the 84 days before it, capped
   between 1.0 and 3.0. Forecast daily demand = velocity × lift.
4. **Cover.** (on hand + in transit) ÷ forecast daily demand, per store and SKU,
   and rolled up per style. In-transit stock counts as arriving.
5. **Targets.** Target stock = forecast × (lead time + 30 days), but never below
   what keeps the category at its min display for the tier.
6. **Warehouse → store.** Needs = target − (on hand + in transit). Warehouse
   on-hand is the supply (inbound deliveries are listed as later supply, not
   spent today). When supply is short, allocate **one unit at a time to the
   store with the lowest projected cover**, so scarce stock goes where it runs
   out first. Capacity headroom (capacity − on hand − in transit − units already
   allocated) caps every store.
7. **Store → store.** For needs the warehouse can't meet: donors are stores with
   excess of that SKU. A donor must keep 30 days of cover for that style after
   the move, keep its category min display, and never give a style in its
   `flagship_protected` list if it is S++. Prefer donors by lead time (same city
   2 days, same zone 4, other zone 7).
8. **Ageing and pull back.** Units whose oldest stock is over 180 days old, in a
   store with over 120 days of cover for that SKU: move to the store that sells
   the style fastest and has headroom, or pull back to the warehouse if no store
   sells it. Stores over capacity pull back their slowest stock first.
9. **Under-stocked stores.** Store-level flags: min display gaps per category,
   and high velocity with low fill.
10. **Priority and reasons.** Each move gets a priority score (rupees of sales at
    risk or stock freed) and a one-line reason from a template with the real
    numbers, e.g. "LKO-01 had KUR-04 in stock only 14 of 84 days and still sold
    12; similar flagships sell 1.3 a day. Send 18 from WH-KOL, arrives 4 Nov."
11. **Independent rule validator.** A separate module re-checks the final list
    against every rule (min display, capacity, flagship protection, in-transit
    not sent twice, donor 30-day cover, approval tag over Rs 1,00,000, no
    excluded data-issue rows). Its result is published with the run. A broken
    rule fails the run.
12. **Briefing (LLM).** The engine passes a small JSON of facts (top moves, data
    issues, store flags, totals) to the LLM, which writes 4 to 6 plain sentences.
    A checker confirms every number in the text appears in the facts; on failure
    it retries once, then falls back to a template. Called only during the run,
    never on a page view.

### Output contract
One JSON file per run, validated by Pydantic in the engine and by Zod in the
web app: `run` (id, data_as_of, generated_at, trigger), `briefing` (text,
source: llm or template, checked), `moves[]` (id, type, sku_id, style_id,
style_name, category, size, from, to, units, value_mrp, lead_days, arrives_on,
priority, reason, needs_senior_approval, numbers{velocity, days_in_stock_84,
cover_before, cover_after, lift}), `rule_check` (per rule: checked, passed,
failures[]), `data_issues[]`, `stores[]` (fill, cover, min display gaps, flags).

## 6. Tech

### Repository (monorepo)
- `engine/`: Python 3.12 (uv), pandas, Pydantic, pytest. CLI `uv run stock-mover run`
  writes `out/latest.json`
- `apps/web`: Next.js (App Router), TypeScript, Tailwind, shadcn/ui, Zod, pnpm
- `data/raw/`: the 17 Manyavar CSVs (committed)
- `apps/web/data/seed-run.json`: a committed engine run, so the site works on
  first open

### LLM
Sarvam AI chat completions (event credits), model from env. Key in env only,
never committed. One call (plus at most one retry) per engine run.

### Daily run
GitHub Actions workflow on a daily cron (06:00 IST) and on manual dispatch:
install, run the engine, call Sarvam, upload `latest.json` to Vercel Blob. It
**never commits to git** (no pushes after 4:45 pm is a hackathon rule). The web
app reads the latest Blob run (revalidated every few minutes) and falls back to
the seed run.

### Deployment
Vercel (web, Root Directory `apps/web`, Git integration on push to `main`).
Secrets: `SARVAM_API_KEY` (GitHub Actions), `BLOB_READ_WRITE_TOKEN` (GitHub
Actions and Vercel). The site needs no sign-in.

## 7. UI/UX

A working tool for a merchandiser, not a dashboard of charts.

- Calm, dense, readable: the list is the hero. Manyavar-inspired warm palette
  (cream background, deep maroon and saffron accents) without using Manyavar's
  logo or brand marks
- One-line reasons in plain words; numbers in a tabular font
- Desktop-first, usable at phone width (no horizontal page scroll at 390 px)
- Keyboard: approve and reject reachable by keyboard; visible focus; reduced
  motion respected

## 8. Security

- No accounts and no personal data (the data has hashed customer IDs; the app
  does not show them)
- API keys in env and CI secrets only; `.env` git-ignored
- The LLM gets engine facts only, never raw tables; its text is checked
- Approvals live in the viewer's browser (localStorage); nothing is sent anywhere

## 9. Out of scope

Store Coach features (salespeople, conversion, rosters), real ERP or WMS
integration, sending moves anywhere (the tool recommends; a human approves),
transport cost (ignored by the rules), accounts, a database, shared approvals
across devices, a chat box, and forecasting beyond the season lift.
