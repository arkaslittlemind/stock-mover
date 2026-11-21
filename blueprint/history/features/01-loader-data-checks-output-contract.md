# Feature: Loader, data checks, output contract

**From build-plan:** feature 1
**Build attempt:** 1
**Branch:** feature/loader-data-checks-output-contract
**Status:** verified

## Goal

Give the engine a trustworthy base: load the 17 Manyavar CSVs as text with
explicit typed conversions, drop packaging SKUs everywhere, find the planted data
errors (KNP-03 SHW-02-L and MYS-02 KUR-02-M) as plain-words data issues that are
excluded from moves, and lock the run JSON output contract as Pydantic models
with an exported JSON Schema that the web app (item 4) mirrors in Zod.

## In scope

- Constants module with the locked values this item needs (`TODAY` = 2026-10-31,
  `WAREHOUSE_ID` = "WH-KOL", data directory default).
- Loader: read every CSV in `data/raw/` with `dtype=str`, `keep_default_na=False`;
  convert the columns the engine uses to int / date explicitly; drop packaging
  SKUs (`items.is_packaging == 1`) from `items` and from every table keyed by
  `sku_id` (`bill_lines`, `stock_snapshot`, `stock_weekly`, `warehouse_inbound`).
- Data checks (pure functions over the loaded frames):
  1. negative stock: snapshot `on_hand < 0` or `in_transit < 0` (any location,
     WH-KOL included);
  2. snapshot vs last weekly close: for store locations (not WH-KOL), snapshot
     `on_hand` vs `stock_weekly.closing_on_hand` at the latest `week_ending`
     (2026-10-31), joined outer with a **missing row = 0** on either side;
  3. join checks: snapshot / weekly / inbound / bill_lines `sku_id` not in
     `items`; snapshot `location_id` not in `stores` and not WH-KOL; weekly /
     bills `store_id` not in `stores`.
- One `DataIssue` per location-SKU (several failed checks merge into one record),
  each with a plain-words note quoting the real numbers, and `excluded = True`.
  An exclusion helper that removes those location-SKU pairs from a frame.
- Pydantic v2 output contract models for the whole run (shapes below) and a
  `stock-mover schema` CLI subcommand that writes the JSON Schema to
  `apps/web/data/run.schema.json` (committed).

## Out of scope

- Velocity, lift, cover, targets, allocation, moves, reasons (items 2, 3, 5).
- Filling `stores[]`, `rule_check`, `briefing` with real values (items 3, 5, 6).
- `stock-mover run` and `out/latest.json` (item 3). Zod schema and any web UI
  (item 4).
- Editing any CSV in `data/raw/` (data problems are flagged, never fixed).

## Build loop

`workflow.stepReview` is `feature`: build all three steps, keeping the test
command green after each, then stop once for review of the whole feature.
`workflow.checkpointCommits` is `disabled`: no commits during the build;
`/complete` makes the single feature commit, then the user pushes.

## Build steps

- [x] **1. Constants and loader.** Add `constants.py` and `loader.py`.
  `load_data(raw_dir: Path = RAW_DIR) -> Dataset` (a frozen dataclass with one
  DataFrame attribute per CSV) reads all 17 CSVs as text, converts typed columns
  (`items`: mrp, cost_price, is_core_style, is_packaging int, launch_date date;
  `stores`: size_sqft, stock_capacity_units int, opened_on date;
  `stock_snapshot`: on_hand, in_transit int, as_of_date date, the two optional
  date columns date-or-missing; `stock_weekly`: closing_on_hand, days_in_stock
  int, week_ending date; `bills`: bill_date date; `bill_lines`: qty, mrp,
  selling_price int; `warehouse_inbound`: qty int, expected_date date;
  `min_display`: min_display_units int; `lead_times`: days int;
  `flagship_protected`: rank int; `calendar`: date date, is_wedding_date int;
  `area_managers`: max_alerts_per_week int). Other tables stay text. Drops
  packaging SKUs as above. A missing file raises `FileNotFoundError` naming it;
  a missing column or a value that does not parse in a typed column raises
  `ValueError` naming file, column and the bad value (no silent coercion).
  Drop `bills.customer_id` at load: the engine never needs it and it must never
  reach the output. *Done when:* `uv run pytest -q` passes with tests that load
  the real data (typed dtypes present, no `is_packaging == 1` SKU left in any
  sku-keyed table) and fixture tests for the missing-file, missing-column and
  bad-integer errors.

- [x] **2. Data checks and exclusion.** Add `checks.py` with one function per
  check plus `find_data_issues(ds: Dataset) -> list[DataIssue]` (merges per
  location-SKU, sorted by location then SKU) and `exclude_pairs(df, issues,
  location_col) -> DataFrame`. Notes are one or two plain sentences with the
  numbers, e.g. "Snapshot shows 300 on hand, but the 31 Oct weekly close shows
  0. Excluded from moves." and "Snapshot shows -4 on hand; stock cannot be
  negative. ... Excluded from moves." *Done when:* `uv run pytest -q` passes with
  (a) one small hand-built fixture per check, including: missing snapshot row vs
  weekly close 0 is **not** flagged, missing snapshot row vs weekly close 5
  **is** flagged, WH-KOL is never compared with the weekly table, two checks on
  one pair give one record; and (b) a real-data test asserting the flagged pairs
  are exactly {(KNP-03, SHW-02-L), (MYS-02, KUR-02-M)}, both notes contain the
  snapshot and weekly numbers, both `excluded` is true, and `exclude_pairs`
  removes exactly those two rows from the snapshot. If the real data flags any
  other pair, stop and report it with its numbers before changing a check (the
  plan says no other pair should be flagged).

- [x] **3. Output contract and schema export.** Add `contract.py` with the models
  in "Data / contracts", `cli.py` with argparse (`stock-mover schema [--out
  PATH]`, default `apps/web/data/run.schema.json` resolved from the repo root),
  point `[project.scripts]` at `stock_mover.cli:main`, remove the hello-world
  `main` from `__init__.py`, add `jsonschema` to the **dev** dependency group
  (`uv add --dev jsonschema`), and generate and commit the schema file. *Done
  when:* `uv run pytest -q` passes with tests that (a) build a sample `Run` with
  one move of each type, one data issue, one store, one rule result, dump it
  `by_alias` and validate it with `jsonschema` against the exported schema;
  (b) assert the dump has `from` / `to` keys (not `from_location`); (c) assert
  `Run.model_validate` round-trips the dump; (d) assert an unknown move `type`
  and an unknown `trigger` are rejected; (e) assert the committed
  `apps/web/data/run.schema.json` equals freshly generated output (drift
  guard); and `uv run stock-mover schema` exits 0 and rewrites the same file.

## Files / areas

- `engine/src/stock_mover/constants.py` (new)
- `engine/src/stock_mover/loader.py` (new)
- `engine/src/stock_mover/checks.py` (new)
- `engine/src/stock_mover/contract.py` (new)
- `engine/src/stock_mover/cli.py` (new)
- `engine/src/stock_mover/__init__.py` (hello-world `main` removed)
- `engine/pyproject.toml`, `engine/uv.lock` (script entry, `jsonschema` dev dep)
- `engine/tests/test_loader.py`, `test_checks.py`, `test_contract.py` (new);
  `test_smoke.py` may stay
- `apps/web/data/run.schema.json` (new, generated)
- `data/raw/` read only

## Data / contracts

The run JSON is the persisted boundary between engine and web app; item 1 locks
its shape. Later items fill it and never reshape it. All models use
`ConfigDict(extra="forbid")`; dump with `model_dump(mode="json", by_alias=True)`.

- `Run`: `run: RunInfo`, `briefing: Briefing`, `moves: list[Move]`,
  `rule_check: list[RuleResult]`, `data_issues: list[DataIssue]`,
  `stores: list[StoreHealth]`.
- `RunInfo`: `id: str`, `data_as_of: date` (ISO `YYYY-MM-DD`), `generated_at:
  AwareDatetime` (ISO 8601 with offset), `trigger: Literal["manual", "schedule",
  "seed"]`.
- `Briefing`: `text: str`, `source: Literal["llm", "template"]`, `checked: bool`.
- `Move`: `id: str`, `type: Literal["warehouse_to_store", "store_to_store",
  "pull_back"]`, `sku_id`, `style_id`, `style_name`, `category`, `size: str`,
  `from_location: str` (alias `from`), `to_location: str` (alias `to`), `units:
  int` (>= 1), `value_mrp: float` (>= 0), `lead_days: int` (>= 0), `arrives_on:
  date`, `priority: float`, `reason: str`, `needs_senior_approval: bool`,
  `numbers: MoveNumbers`. Models set `populate_by_name=True` so engine code can
  use the Python names.
- `MoveNumbers`: `velocity: float`, `days_in_stock_84: int` (0 to 84),
  `cover_before: float | None`, `cover_after: float | None`, `lift: float`.
  Cover is `null` when forecast demand is 0 (JSON has no infinity).
- `RuleResult`: `rule: str` (short id, e.g. `min_display`), `label: str`,
  `checked: int` (>= 0), `passed: bool`, `failures: list[str]`.
- `DataIssue`: `location_id: str`, `sku_id: str`, `checks:
  list[Literal["negative_stock", "snapshot_vs_weekly", "unknown_sku",
  "unknown_location"]]` (non-empty), `note: str`, `excluded: bool`.
- `StoreHealth`: `store_id`, `city`, `zone`, `tier: str`, `capacity_units: int`,
  `units_on_hand: int`, `units_in_transit: int`, `fill_pct: float`,
  `days_of_cover: float | None`, `min_display_gaps: list[MinDisplayGap]`,
  `flags: list[str]`.
- `MinDisplayGap`: `category: str` (the `min_display` category, e.g.
  "Accessories (Safa/Mala/Stole)"), `min_display_units: int`, `units: int`,
  `gap: int`.
- Move `id` and run `id` generation belong to item 3; item 1 only types them.
- `checks` on `DataIssue` is a small addition to the overview's "location, SKU,
  plain-words note, excluded flag" so the page and tests can tell checks apart
  without parsing notes.

## Testing

Test command: `cd engine && uv run pytest -q` (gate for every step here; all
three steps are logic). Before this feature it reports `1 passed`. Fixture tests
use small hand-built DataFrames or a temp directory of tiny CSVs; real-data tests
read `data/raw/` through `load_data()`. No browser or web checks in this item;
the schema file is the only web-side artifact and is guarded by the drift test.

## Notes for the AI

- pandas 3 is installed: `dtype=str` yields the string dtype; convert with
  explicit parsing that raises on bad values (`pd.to_numeric(..., errors="raise")`
  wrapped to re-raise with file and column, `pd.to_datetime(..., format="%Y-%m-%d")`
  then `.dt.date`). Empty strings are allowed only in
  `in_transit_arrives_on` and `oldest_stock_received_on`.
- WH-KOL appears in `stock_snapshot` but is not a store; it is valid in the
  snapshot join check and skipped by the weekly comparison.
- The latest weekly close is the max `week_ending` in the data (expected
  2026-10-31); derive it, do not hard-code a second date.
- Keep IO in `loader.py` and `cli.py`; checks and contract stay pure.
- Packaging SKU ids start with `PKG-` in the data, but filter on
  `items.is_packaging`, not the prefix.
- Never display or emit `customer_id`.
- Add `apps/web/data/` with only the schema file; `seed-run.json` arrives in
  item 3.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":10785,"specSha256":"0c35c34560f1bd66f12c219dc8b1ff20cf4844023f6b91db4492885bf176cc63","branch":"refs/heads/feature/loader-data-checks-output-contract","head":"91d0ec9951d837f4e766946c4572ebb24735b209","baseRef":"refs/heads/main","baseCommit":"91d0ec9951d837f4e766946c4572ebb24735b209","sourceTree":"bcf7752d272134144e07a53f8922b069b1934961","landing":"local-merge","absentOptional":[]} -->

## Try it now

```
cd engine
uv run python -c "from stock_mover.loader import load_data; from stock_mover.checks import find_data_issues; [print(i.location_id, i.sku_id, '|', i.note) for i in find_data_issues(load_data())]"
```

Expected output:

```
KNP-03 SHW-02-L | Snapshot shows 300 on hand, but the 31 Oct weekly close shows 0. Excluded from moves.
MYS-02 KUR-02-M | Snapshot shows -4 on hand; stock cannot be negative. Snapshot shows -4 on hand, but the 31 Oct weekly close shows 3. Excluded from moves.
```
