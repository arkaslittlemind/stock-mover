# Feature: Velocity, season lift, cover

**From build-plan:** feature 2
**Build attempt:** 1
**Branch:** feature/velocity-season-lift-cover
**Status:** verified

## Goal

Give the engine an honest demand number for every store-SKU: sales per day in
stock over the last 84 days (so stock-outs do not hide demand), peer velocity
where history is too thin, a per-zone season lift for the coming wedding season,
and the resulting forecast and days of cover per store-SKU and per store-style.
Item 3 (warehouse to store) consumes this; nothing new appears on the page yet.

## In scope

- Constants for the demand rules in `constants.py`.
- Own velocity per store-SKU: units sold in the 84-day window ÷ days in stock in
  that window.
- Peer velocity when days in stock < 14, the store opened < 60 days ago, or the
  style launched < 30 days ago.
- Per-zone season lift, capped 1.0 to 3.0.
- Forecast daily demand = velocity × zone lift; cover = (on hand + in transit) ÷
  forecast, per store-SKU and rolled up per store-style.
- One entry point `build_demand(ds, issues)` returning both tables.

## Out of scope

- Targets, needs, allocation, moves, reasons, `out/latest.json` (item 3).
- Donor cover checks, ageing, store health strip values (item 5).
- Any change to the run contract (`contract.py`) or the JSON Schema.
- Warehouse inbound supply (engine-internal, used later if at all).
- Any web app change.

## Build loop

`workflow.stepReview` is `feature`: build all steps, then one review at the end.
`workflow.checkpointCommits` is `disabled`: no commits per step; `/complete`
makes the single feature commit. Run `uv run pytest -q` (from `engine/`) after
every step; it must stay green.

## Build steps

- [x] **1. Window, days in stock and own velocity.** Add constants
  `VELOCITY_WINDOW_DAYS = 84`, `PEER_MIN_DAYS_IN_STOCK = 14`,
  `NEW_STORE_DAYS = 60`, `NEW_STYLE_DAYS = 30`, `LIFT_AFTER_DAYS = 30`,
  `LIFT_MIN = 1.0`, `LIFT_MAX = 3.0`. Create `engine/src/stock_mover/demand.py`
  with a pure function that builds the store-SKU base table: every store in
  `stores` × every non-packaging SKU in `items` (missing sales or weekly rows =
  0), with `units_84` (sum of `bill_lines.qty` for bills dated
  `TODAY - 83 days` to `TODAY` inclusive, i.e. 9 Aug to 31 Oct 2026),
  `days_in_stock_84` (sum of `stock_weekly.days_in_stock` over the 12 weeks
  ending 15 Aug to 31 Oct 2026, clipped to 0..84), and `own_velocity` =
  `units_84 / days_in_stock_84` (0.0 when days in stock is 0). Functions take
  DataFrames and `today` as arguments so fixtures stay small.
  *Done when:* a fixture test proves a SKU in stock 14 of 84 days that sold 14
  units gets velocity 1.0 (not 14/84); a fixture with sales outside the window
  ignores them; and a real-data test checks 3 real store-SKUs against expected
  values hand-computed from the raw CSV rows (computed once with the `csv`
  module or a spreadsheet during implementation, hard-coded in the test with
  their source rows noted). `uv run pytest -q` passes.

- [x] **2. Peer velocity.** A store-SKU uses peer velocity when
  `days_in_stock_84 < 14`, or `(TODAY - opened_on).days < 60`, or
  `(TODAY - launch_date).days < 30` for its style. Qualifying peers for that SKU
  are other stores of the same tier that are not new (open ≥ 60 days) and have
  `days_in_stock_84 ≥ 14` for it. Use same-zone peers first; if none, same-tier
  peers across the network. Peer rate = Σ peer `units_84` ÷ Σ peer
  `days_in_stock_84` (pooled). Scale it by the store's selling rate relative to
  those peers: store rate = the store's total `units_84` across all SKUs ÷ its
  days open in the window (`min(84, (TODAY - opened_on).days + 1)`); scale =
  store rate ÷ mean store rate of the qualifying peers. When the store has no
  sales in the window, scale = 1.0. When no qualifying peer exists anywhere in
  the tier, keep `own_velocity`. Record `velocity` and `velocity_source`
  (`own`, `peer_zone`, `peer_network`, `own_thin`) on each row.
  *Done when:* fixture tests prove: a store with < 14 days in stock takes the
  same-zone peer rate; it falls back to network peers when its zone has none; a
  new store and a new style use peers even with ≥ 14 days; the scale factor is
  applied; `own_thin` is used when no peer qualifies. A real-data test proves
  no BLR-05 row uses `own`, every BLR-05 row whose SKU has a qualifying B-tier
  peer uses a `peer_*` source, and the rest are `own_thin` (user decision,
  Nov 21: 120 of 382 BLR-05 SKUs are not stocked 14+ days in any B store, so
  0 demand is honest). `uv run pytest -q` passes.

- [x] **3. Season lift, forecast, cover, entry point.** Per zone, the lift =
  (units sold in that zone's stores from 1 to 30 Nov 2025 ÷ 30) ÷ (units sold
  from 9 Aug to 31 Oct 2025 ÷ 84), clipped to 1.0..3.0 (matching date = 31 Oct
  2025, the same calendar day last year; dates derive from `TODAY` and the
  constants, not literals). A zone with no sales in the before window gets 1.0.
  Add `lift`, `forecast_daily` = `velocity × lift`, `on_hand` and `in_transit`
  from the snapshot (missing row = 0), and `cover_days` = (on hand + in
  transit) ÷ forecast (`None` when forecast is 0). Roll up a store-style table:
  Σ stock ÷ Σ forecast per store and style (same `None` rule). Add
  `build_demand(ds, issues) -> Demand` (a frozen dataclass with `skus`,
  `styles`, `zone_lift`) that drops excluded data-issue location-SKUs with
  `exclude_pairs` before peers are chosen, so an excluded pair is never a peer
  and has no demand row.
  *Done when:* fixture tests prove lift capping at both ends and the zero-sales
  fallback, cover = stock ÷ forecast, `None` cover for zero forecast, and the
  style roll-up. Real-data tests prove: each zone lift is within 1.0..3.0;
  LKO-01 KUR-04 rows use a `peer_*` source and its style forecast is above the
  median KUR-04 style forecast across all stores; KNP-03 SHW-02-L and
  MYS-02 KUR-02-M have no demand row. `uv run pytest -q` passes.

## Files / areas

- `engine/src/stock_mover/constants.py` - new demand constants.
- `engine/src/stock_mover/demand.py` - new: base table, own and peer velocity,
  zone lift, forecast, cover, `build_demand`.
- `engine/tests/test_demand.py` - new: fixture and real-data tests.
- Reads only: `loader.py` (`Dataset`), `checks.py` (`find_data_issues`,
  `exclude_pairs`), `contract.py` (`DataIssue`).

## Data / contracts

- No change to the run JSON contract or `apps/web/data/run.schema.json`.
- `Demand.skus` (pandas DataFrame, one row per non-excluded store-SKU):
  `store_id`, `sku_id`, `style_id`, `category`, `size`, `tier`, `zone`,
  `units_84` (int), `days_in_stock_84` (int 0..84), `own_velocity` (float),
  `velocity` (float), `velocity_source` (str), `lift` (float),
  `forecast_daily` (float), `on_hand` (int), `in_transit` (int),
  `cover_days` (float or None).
- `Demand.styles`: `store_id`, `style_id`, `stock` (int), `forecast_daily`
  (float), `cover_days` (float or None).
- `Demand.zone_lift`: `dict[str, float]` keyed by zone name.
- Item 3 maps `velocity`, `days_in_stock_84`, `cover_days` and `lift` into the
  existing `MoveNumbers` fields; this feature does not.
- Warehouse `WH-KOL` is not a store and gets no demand rows.

## Testing

- `cd engine && uv run pytest -q` is the gate. Baseline before this feature:
  26 passed (observed).
- Fixture tests build tiny DataFrames directly and call the pure functions with
  an explicit `today`; no fixture writes CSVs.
- Real-data tests reuse a module-scoped `load_data()` fixture (as in
  `test_loader.py`) and call `build_demand` once per module.
- No web or browser checks: nothing user-visible changes.

## Notes for the AI

- Follow the existing engine style: pandas, type hints, small pure functions,
  module docstring, no new dependencies.
- `bill_lines` joins to `bills` on `bill_id` for `bill_date` and `store_id`.
  `stock_weekly` uses `store_id`; `stock_snapshot` uses `location_id` and also
  holds `WH-KOL` rows, which must not become store rows.
- Peer and scale choices above (pooled peer rate, store-level scale against the
  mean peer store rate, `own_thin` fallback) are this spec's reading of the
  project plan's "scaled by the store's share of its peers' total sales". Keep
  them; they are internal and reversible.
- The season-lift matching date follows the overview's stated assumption
  (31 Oct last year). Do not use the calendar wedding dates.
- If a real-data assertion in a done-when fails, stop and report the numbers;
  do not loosen the assertion to pass.
- Record the three hand-computed store-SKUs and how they were computed in the
  test, so `/check` can re-derive them.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":8660,"specSha256":"3a772e40c5dca2bf8d437574f505425ea6c4bb68d1d7a720cbfd570d278a6871","branch":"refs/heads/feature/velocity-season-lift-cover","head":"9d710d6a68d1c901e37e2840262aa64d9d05b0c9","baseRef":"refs/heads/main","baseCommit":"9d710d6a68d1c901e37e2840262aa64d9d05b0c9","sourceTree":"7e0825ccf4b0b74d95e924d47e975b0a525114f2","landing":"local-merge","absentOptional":[]} -->
