# Feature: Warehouse → store + seed run

**From build-plan:** feature 3
**Build attempt:** 1
**Branch:** feature/warehouse-store-seed-run
**Status:** verified

## Goal

Turn item 2's demand table into warehouse-to-store moves: a target per
store-SKU, needs net of stock already in transit, scarce warehouse units shared
one unit at a time to the store with the lowest projected cover, capacity caps,
min display top-ups, the Rs 1,00,000 approval tag, a priority and a one-line
reason with real numbers. A new CLI command `uv run stock-mover run` writes a
contract-valid run JSON to `out/latest.json`, and a committed copy at
`apps/web/data/seed-run.json` gives item 4 real data to show.

## In scope

- Lead days per store from `lead_times.csv` (warehouse row for the store's zone:
  East 3, North 4, South 6).
- Warehouse supply = `WH-KOL` on hand per SKU from the snapshot. Inbound
  deliveries are not spent (project plan §5.6).
- Target per store-SKU = forecast × (lead days + 30), rounded half up to whole
  units. Need = max(0, target − (on hand + in transit)).
- Min display floor per store and display category ("Accessories
  (Safa/Mala/Stole)" = Safa + Mala + Stole), filled from the warehouse before
  demand needs.
- Capacity headroom per store = capacity − (on hand + in transit) − units
  already allocated in this run. Never negative; a store at or over capacity
  gets nothing.
- Moves of type `warehouse_to_store`, one per store-SKU, with every contract
  field filled.
- `stock-mover run` CLI subcommand and the committed seed run.

## Out of scope

- Store-to-store, ageing and pull-back moves, the rule validator, store health
  (`stores[]`) and under-stocked flags: item 5. This item writes
  `rule_check: []` and `stores: []`.
- The LLM briefing: item 6. This item writes a short template briefing.
- Spending inbound deliveries, Blob upload, GitHub Actions: item 7.
- Any web app change other than adding the seed JSON file (the page is item 4).
- Changing the output contract or the JSON Schema.

## Build loop

`workflow.stepReview` is `feature` and `workflow.checkpointCommits` is
`disabled`: build all steps in order on branch
`feature/warehouse-store-seed-run`, run `uv run pytest -q` after each step, no
per-step commits, one review at the end. `/complete` makes the feature commit.

## Build steps

- [x] **1. Targets, needs, supply and headroom.** New module
  `engine/src/stock_mover/allocate.py`. Add constants `TARGET_EXTRA_DAYS = 30`,
  `SENIOR_APPROVAL_MRP = 100_000`, `OUT_PATH = REPO_ROOT / "out" / "latest.json"`,
  `SEED_RUN_PATH = REPO_ROOT / "apps" / "web" / "data" / "seed-run.json"` and the
  display-category map (`Safa`, `Mala`, `Stole` → `Accessories (Safa/Mala/Stole)`,
  every other category maps to itself). Functions:
  - `warehouse_lead_days(stores, lead_times)`: store_id → days, matching the
    store's zone to the `Warehouse WH-KOL to store, <Zone> zone` route. A store
    zone with no route raises `ValueError` naming the zone.
  - `warehouse_supply(snapshot, issues)`: sku_id → `WH-KOL` on hand, with
    data-issue pairs at `WH-KOL` excluded and non-positive values dropped.
  - `store_headroom(skus, stores)`: store_id → max(0, capacity − sum of on hand
    + in transit) using the demand table, so excluded data-issue rows (KNP-03's
    300 sherwanis) do not count.
  - `add_targets(skus, lead_days)`: adds `lead_days`, `target`, `need` columns.
  *Done when:* fixture tests in `engine/tests/test_allocate.py` prove a store-SKU
  whose in-transit covers its target has need 0 (in-transit never resent), a
  zero-forecast store-SKU has target 0, the target rounds half up, an excluded
  warehouse pair adds no supply, headroom ignores excluded rows and is never
  negative, and an unknown zone raises; `uv run pytest -q` passes.

- [x] **2. Allocation: min display, then fair share.** In `allocate.py`,
  `allocate(skus, supply, headroom, min_display, items)` returns units per
  (store_id, sku_id) plus the units that came from the min display phase.
  - Phase A, min display: for each store and display category where on hand + in
    transit + allocated < the tier's `min_display_units`, add one unit at a time
    to a SKU of that category with warehouse supply left, choosing the SKU with
    the fewest units at that store (stock + allocated), then the highest
    forecast, then `sku_id`. Stop when the gap closes, supply for the category
    runs out, or the store has no headroom.
  - Phase B, fair share: repeatedly give one unit to the store-SKU with remaining
    need (need minus units already given, counting phase A units), warehouse
    supply left and store headroom left, picking the lowest projected cover
    `(on hand + in transit + allocated) / forecast`, ties broken by higher
    forecast, then `store_id`, then `sku_id` (a heap keyed on that tuple).
  - Deterministic: the same inputs give the same output.
  *Done when:* fixture tests prove the total sent per SKU never exceeds warehouse
  supply; the total sent per store never exceeds its headroom; with 3 stores
  needing the same SKU and supply for 2 units, those units go to the
  lowest-cover stores in order; a store with a min display gap and no forecast
  still gets top-up units; a store at capacity gets nothing; `uv run pytest -q`
  passes.

- [x] **3. Moves, run file and seed run.** In `allocate.py`,
  `warehouse_moves(allocation, skus, items, lead_days, today)` builds contract
  `Move` objects, and new `engine/src/stock_mover/run.py` has
  `build_run(ds, now, trigger)` that loads issues and demand, allocates, and
  returns a `Run`. Extend `cli.py` with `run --out PATH (default OUT_PATH)
  --trigger manual|schedule|seed (default manual)`, writing indented JSON by alias
  with LF line endings. Then generate the seed file with
  `uv run stock-mover run --trigger seed --out ../apps/web/data/seed-run.json`.
  *Done when:* tests in `engine/tests/test_run.py` on the real data prove: the
  run validates against `apps/web/data/run.schema.json` and parses as `Run`;
  KUR-01's warehouse units (50 across its sizes) are all sent, and for every
  KUR-01 SKU no store left with unmet need had a lower projected cover than the
  last unit given (unless that store had no headroom); MZF-01 gets at least one
  move whose reason names min display and the Mojari gap; BLR-05 gets at least
  one min display top-up move; LKO-01 gets at least one KUR-04 move; every move
  has `needs_senior_approval == (value_mrp > 100000)`, `arrives_on == today +
  lead_days`, `units >= 1`, a unique `id`; no move touches a data-issue pair;
  `apps/web/data/seed-run.json` exists, validates against the schema and has
  `trigger: "seed"`; `uv run pytest -q` passes.

## Files / areas

- `engine/src/stock_mover/constants.py` - new constants (step 1).
- `engine/src/stock_mover/allocate.py` - new (steps 1 to 3).
- `engine/src/stock_mover/run.py` - new (step 3).
- `engine/src/stock_mover/cli.py` - `run` subcommand (step 3).
- `engine/tests/test_allocate.py`, `engine/tests/test_run.py` - new.
- `apps/web/data/seed-run.json` - generated and committed (step 3).
- `out/` is already in `.gitignore`.
- Reuse: `loader.load_data`, `checks.find_data_issues` / `exclude_pairs`,
  `demand.build_demand` (its `skus` table has `forecast_daily`, `on_hand`,
  `in_transit`, `cover_days`, `velocity`, `days_in_stock_84`, `lift`, `tier`,
  `zone`, `category`, `size`, `style_id`), `contract.Run` and friends.

## Data / contracts

The output contract is locked (item 1); this item fills it, never reshapes it.

- `run.id` = `"<data_as_of>-<generated_at as %Y%m%dT%H%M%SZ in UTC>"`;
  `data_as_of` = `TODAY`; `generated_at` = the `now` passed in (timezone-aware,
  UTC; the CLI passes the current time, tests pass a fixed time); `trigger` from
  the CLI.
- `briefing` = template text built from run totals (moves, units, value at MRP,
  moves needing senior approval, data issues excluded), `source: "template"`,
  `checked: true`. Item 6 replaces it.
- Each move: `id` = `"w2s-<store_id>-<sku_id>"`; `type` = `warehouse_to_store`;
  `from` = `WH-KOL`; `to` = store; `units` = units allocated; `value_mrp` =
  units × item MRP; `lead_days` from step 1; `arrives_on` = today + lead days;
  `needs_senior_approval` = value_mrp > 1,00,000; `priority` = value_mrp of the
  units (rupees of sales at risk), rounded to 2 decimals; `numbers.velocity`,
  `numbers.lift` rounded to 2 decimals, `numbers.days_in_stock_84` from demand,
  `cover_before` = (on hand + in transit) / forecast and `cover_after` = (on
  hand + in transit + units) / forecast, rounded to 1 decimal, `None` when the
  forecast is 0.
- Moves sorted by priority descending, then `id`.
- `reason`: one line from a template with real numbers, ending with "Send <units>
  from WH-KOL, arrives <d Mon>." The opening clause depends on why:
  - any min display units in the move: "<store> has <n> <display category> on display vs a
    minimum of <min> for a <tier> store."
  - thin history (`velocity_source` `peer_zone` / `peer_network`): "Similar
    <tier> stores sell <velocity> a day of <sku>; <store> has <cover_before>
    days of cover."
  - own velocity with days in stock < 84: "<store> had <sku> in stock only <d>
    of 84 days and still sold <units_84>; <cover_before> days of cover."
  - otherwise: "<store> sells <forecast> a day of <sku> (season lift <lift>);
    <cover_before> days of cover vs <lead + 30> needed."
  A move that mixes min display and demand units uses the min display clause
  (revised during implement: otherwise MZF-01's Mojari top-up, which also has
  demand units, never names the min display gap).
  Zero-forecast cover reads "no recent sales" instead of a number.
- `rule_check: []`, `stores: []` (item 5). `data_issues` from
  `find_data_issues`.
- JSON written with `model_dump(mode="json", by_alias=True)`, `indent=2`,
  UTF-8, LF.

## Testing

- Test command: `uv run pytest -q` from `engine/` (gate). Baseline before this
  feature: 50 passed.
- Logic tests on small hand-built DataFrames in `test_allocate.py` (no CSVs).
- Real-data tests in `test_run.py` build the run once per module (module-scoped
  fixture) with a fixed `now`.
- Schema validation uses the existing `jsonschema` dev dependency.
- No web build change is expected; the seed JSON is data only until item 4.

## Notes for the AI

- Store stock for headroom and min display comes from the demand table, which
  already drops data-issue pairs, so KNP-03 is not treated as over capacity.
- Warehouse holds only 1 Sherwani unit, so BLR-05's Sherwani gap (2 vs 5)
  cannot fully close from the warehouse; that is expected. Store-to-store
  (item 5) handles the rest. BLR-05's top-up done-when is satisfied by any min
  display move.
- Rounding target half up: `math.floor(x + 0.5)`; do not use Python `round`
  (banker's rounding).
- Phase A runs before phase B because the target is floored at min display
  (project plan §5.5); phase A units count toward the store-SKU's need.
- Keep the heap tuple deterministic; never iterate a set or dict without
  sorting where order changes the result.
- Do not edit `contract.py` or `run.schema.json`. If a contract gap appears,
  stop and raise it.
- Dates in reasons: `f"{d.day} {d:%b}"` (the existing `checks._fmt_date` style).


<!-- blueprint:completion {"schemaVersion":2,"specBytes":11281,"specSha256":"28bc72024f8b511f01fe8a94db8b299f2cc9612b2d1bd72894513b918bb2d56c","branch":"refs/heads/feature/warehouse-store-seed-run","head":"d352f48fca29681d0cdbf95e61f8b5d986348c53","baseRef":"refs/heads/main","baseCommit":"d352f48fca29681d0cdbf95e61f8b5d986348c53","sourceTree":"bd221d293224c437e58328304f2055940736c5c5","landing":"local-merge","absentOptional":[]} -->

## Try it now

Run or do:

```
cd engine
uv run stock-mover run
```

Expected:

```
Wrote ...outlatest.json: 810 moves, 2 data issues
```

The first move in `out/latest.json` is `w2s-LKO-01-KUR-04-XL` (45 units, reason
"Similar S++ stores sell 1.5 a day of KUR-04-XL; LKO-01 has 0.0 days of cover.
Send 45 from WH-KOL, arrives 4 Nov.").

This proves: the CLI writes a run file with warehouse-to-store moves and
readable reasons, and the hidden KUR-04 demand at LKO-01 is the top move.
