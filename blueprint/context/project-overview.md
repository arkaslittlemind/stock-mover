# Stock Mover - Project Overview

<!-- blueprint:source-hash fa655402c7990fe83c2e1261790c265d50771711454d0964f8a379cb657798a2 -->

> A daily engine that turns Manyavar sales and stock data into a ready-to-approve list of stock moves, each with a one-line reason and an independent rule check, shown on a public page.

## Problem

Stock sits in the wrong place: hero styles stock out in flagships while small stores hold the same style for months, and new styles look slow only because the stores that would sell them never got any. A merchandiser works this out by hand across 20 stores, a warehouse (WH-KOL) and 385 SKUs, under rules on min display, capacity, flagship styles and donor cover. Stock Mover runs every morning on its own and produces a list that can be approved in ten minutes.

## Users

- **Merchandiser (primary)** - reviews the list each morning, approves or rejects moves, exports the approved list.
- **Area manager** - filters the list to their city and stores.
- **Judges and Manyavar reviewers** - check the hidden problems were found, spot-check numbers, confirm no rule is broken and that it runs unattended.

All access is anonymous; there are no accounts.

## Usage model

- Public, no sign-in, read-only data (synthetic, owned by Vedant Fashions Limited).
- No accounts, no personal data shown (hashed customer IDs are never displayed), no database, no shared approvals across devices.
- Approvals live only in the viewer's browser (localStorage); nothing is sent anywhere.
- The LLM sees engine facts only, never raw tables; page views never call it.
- Secrets in env and CI secrets only.

## Features

Build order from `build-plan.md`. Headline: the approve page (item 4) backed by the engine (items 1 to 3, 5).

1. **Loader, data checks, output contract** - typed CSV loading, packaging dropped, missing snapshot rows = 0, data issues flagged and excluded (KNP-03 SHW-02-L, MYS-02 KUR-02-M), Pydantic output models plus JSON Schema export.
2. **Velocity, season lift, cover** - per-day-in-stock velocity over 84 days, peer velocity for thin history, per-zone season lift (1.0 to 3.0), forecast and cover per store-SKU and per style.
3. **Warehouse to store + seed run** - targets, needs net of in-transit, one-unit-at-a-time fair share by lowest projected cover, capacity caps, approval tag, reasons; CLI writes `out/latest.json`, copied to `apps/web/data/seed-run.json`.
4. **Approve page on the live URL** (headline) - grouped moves, reasons, expandable numbers, approve/reject per move and group, filters, export approved CSV, data issues panel, run info, Zod-validated with an error state.
5. **Store to store, ageing, pull back, rule validator** - donor rules, ageing and over-capacity pull backs, independent validator published in the run, store health strip.
6. **LLM briefing with number check** - Sarvam call from the engine, every number checked against facts, one retry, template fallback.
7. **Runs on its own** - GitHub Actions daily cron (06:00 IST) and manual dispatch upload `latest.json` to Vercel Blob with no git commit; web reads Blob with seed fallback.

## Engine rules (locked constants)

| Rule | Value |
|---|---|
| Today | close of 31 Oct 2026 |
| Velocity window | 84 days, units / days in stock (`stock_weekly.days_in_stock`) |
| Peer velocity when | days in stock < 14, store open < 60 days, or style launched < 30 days |
| Peers | same tier, same zone first, else network, scaled by store share of peer sales |
| Season lift | per zone, last year 30 days after / 84 days before matching date, capped 1.0 to 3.0 |
| Target | forecast x (lead time + 30 days), floored at category min display for the tier |
| Donor | keeps 30 days of style cover and category min display; S++ never gives a `flagship_protected` style |
| Donor lead preference | same city 2 days, same zone 4, other zone 7 |
| Ageing | oldest stock > 180 days and > 120 days of cover |
| Senior approval | move value at MRP > Rs 1,00,000 |
| Validator | a broken rule fails the run |

## Data model

### Inputs (`data/raw/`, read-only, committed)

17 CSVs from the Manyavar pack. Key tables: `items` (SKU, style, category, size, MRP, `is_packaging`), `stores` (tier, zone, city, capacity, open date), `stock_snapshot` (location-SKU on hand, in transit, stock age; missing row = 0), `stock_weekly` (weekly close, `days_in_stock`), `bills` + `bill_lines` (sales), `warehouse_inbound`, `min_display` (per tier and category; "Accessories (Safa/Mala/Stole)" sums three `items` categories), `lead_times`, `flagship_protected`, `rules`, `calendar`, `area_managers`. IDs are text. Packaging SKUs are excluded everywhere.

### Run (output contract, one JSON per run)

Validated by Pydantic in the engine and Zod in the web app. Locked from item 1; later items fill it, never reshape it.

- `run` - `id` (str), `data_as_of` (date), `generated_at` (datetime), `trigger` (str: manual, schedule, seed)
- `briefing` - `text` (str), `source` (`llm` | `template`), `checked` (bool)
- `moves[]` - `id`, `type` (warehouse_to_store, store_to_store, pull_back), `sku_id`, `style_id`, `style_name`, `category`, `size`, `from`, `to`, `units` (int), `value_mrp` (number), `lead_days` (int), `arrives_on` (date), `priority` (number), `reason` (str), `needs_senior_approval` (bool), `numbers` {`velocity`, `days_in_stock_84`, `cover_before`, `cover_after`, `lift`}
- `rule_check` - per rule: `checked` (int), `passed` (bool), `failures[]`
- `data_issues[]` - location, SKU, plain-words note, excluded flag
- `stores[]` - fill vs capacity, days of cover, min display gaps, flags (under-stocked)

### Browser state

- Approvals: localStorage keyed by run id and move id, value approved or rejected.

## Tech stack

- **Python 3.12 + uv, pandas, Pydantic, pytest** (`engine/`) - deterministic engine; all numbers and rule checks are code.
- **Next.js App Router, TypeScript, Tailwind v4, shadcn/ui, Zod, pnpm** (`apps/web/`) - the approve page.
- **Sarvam AI chat completions** - briefing text only, model from `SARVAM_MODEL`.
- **GitHub Actions + Vercel Blob** - daily unattended run and published result.

## Monetization

Not in scope for the hackathon MVP (the plan has no monetization section).

## UI/UX

- `/` - Today's list: briefing, rule check badge, store health strip, three move groups with approve/reject, filters, export, data issues panel, run info ("Data as of 31 Oct 2026 close, generated automatically at <time> by the daily run").
- Calm, dense, list is the hero. Warm palette (cream, deep maroon, saffron), no Manyavar logo or brand marks. Numbers in a tabular font.
- Desktop-first, no horizontal scroll at 390 px, keyboard-reachable approve/reject, visible focus, reduced motion respected.

## Deployment

- **Web:** Vercel project `stock-mover`, Root Directory `apps/web`, Git integration deploys every push to `main`. Live at https://stock-mover.vercel.app, no sign-in.
- **Daily run:** GitHub Actions, cron 06:00 IST plus manual dispatch; never commits to git.
- **Env vars:** `SARVAM_API_KEY` and `SARVAM_MODEL` (GitHub Actions), `BLOB_READ_WRITE_TOKEN` (GitHub Actions and Vercel).
- **Fallback:** committed `apps/web/data/seed-run.json` so the page works on first open.
- **Hard stop:** no commits or pushes after 4:45 pm IST, 21 Nov 2026.

## Open questions

- Season lift "matching date" is not pinned: assume the 30 days after 31 Oct last year vs the 84 days before it, unless item 2's spec says otherwise.
- `from` is a Python keyword: the Pydantic model needs field aliases (`from_location` with alias `from`) so the JSON keeps `from`/`to`.
- Inbound warehouse deliveries are "later supply, not spent today" (project plan) but no build item shows them on the page; treat as engine-internal unless added.
- Out of scope (confirmed): Store Coach features, ERP/WMS integration, sending moves anywhere, transport cost, accounts, database, shared approvals, chat box, forecasting beyond the season lift.
