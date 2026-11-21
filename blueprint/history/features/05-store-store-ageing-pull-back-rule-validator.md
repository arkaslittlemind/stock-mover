# Feature: Store → store, ageing, pull back, rule validator

**From build-plan:** feature 5
**Build attempt:** 1
**Branch:** feature/store-store-ageing-pull-back-rule-validator
**Status:** verified

## Goal

Turn the warehouse allocation into a complete, independently checked list for the merchandiser. Fill remaining store demand from eligible donors, consolidate ageing stock where it sells, pull stock back to WH-KOL when needed, and show the health of each store.

## In scope

- Store transfers, ageing transfers, and ageing and over-capacity pullbacks. Preserve warehouse fair share and the existing min-display top-up.
- Independent validation of the complete list. A broken rule fails generation before a run file is written. Successful runs include per-rule results.
- Current store fill, cover, category display gaps and under-stocked flags. Show these on the public Dispatch page alongside the existing rule badge and three move groups.
- Regenerate the checked-in seed. After approval and landing, push within the hackathon deadline and verify the public page.

## Out of scope

- Sarvam briefing, scheduled jobs, Blob, and changes to approvals or the run schema.

## Build loop

Feature-level approval and the product decisions below were confirmed on 21 Nov 2026. Review the complete feature together and keep checkpoint commits disabled. Run the Blueprint check and the build-plan audit before completion. The final feature commit belongs to the completion step.

## Build steps

- [x] **1. Rebalance unmet SKU needs after warehouse allocation.** Reuse the demand, targets, min-display mapping and warehouse plan. Track eligible source on-hand, destination needs, projected stock and destination headroom across accepted recommendations. For each remaining need, choose donors holding excess of that SKU in ascending lead time (same city 2 days, same zone 4, other zone 7). Bound each transfer by remaining need, available donor units, receiving headroom, donor category display and 30 days of donor style cover. Enforce S++ protection by store and style. Use stable keys to break lead-time ties. **Done when** focused pytest fixtures show a warehouse shortfall can be filled by the nearest eligible donor and show cumulative stock, in-transit, capacity, category display, donor cover and flagship limits binding. Existing warehouse cases still pass.
- [x] **2. Plan ageing and capacity relief.** Map snapshot receipt ages onto eligible store-SKUs. Apply the strict age and SKU cover thresholds to the remaining stock. Rank other stores with headroom by the style's sales velocity. Route eligible stock to the fastest seller that can receive it, or to WH-KOL when no qualifying destination can receive it. Pull back remaining over-capacity stock slowest first. Every giving store retains its display minimum and every S++ store retains its protected styles. The 30-day style-cover floor applies to all store-to-store transfers. Count all recommendations already planned when deciding what can move. Use one-line reasons with actual ages, cover, capacity or sales figures as applicable. **Done when** pytest covers exact threshold boundaries, zero demand with adequate stock exposure, recipient ranking and lack of headroom, cumulative constraints, and slowest-first capacity relief. The real list includes ageing recommendations for JKT-08 and IW-08.
- [x] **3. Independently validate the final list and publish store health.** Validate from cleaned inputs, the existing demand calculation, and the final moves. Reconstruct totals independently of allocation counters and presentation order. Check donor display and style cover, store capacity, flagship protection, in-transit counted once and excluded from shippable supply, total outbound against original on-hand, senior approval over Rs 1,00,000, and exclusion of quarantined pairs at either endpoint. Check move type and endpoints, units and MRP arithmetic, and lead time and arrival against the applicable route. A store with a pre-existing display gap can receive stock. Document how unavoidable pre-existing over-capacity is handled after review. Return rule names, labels, counts and actionable failures. Surface a failed rule as a nonzero CLI exit before creating or replacing the output file. Build store health from the cleaned snapshot and forecast, and update the template briefing to describe the combined list accurately. **Done when** each executable rule has a failing fixture, including cumulative failures where single moves are individually valid. A failure preserves a previous output. The real run reports zero failures, no S++ protected style leaves its store, all stores are represented, and the output validates against the checked-in schema.
- [x] **4. Ship the run through the approve page.** Regenerate the seed via the existing CLI with the seed trigger. Use the validated run to render a compact store health strip with stock against capacity, cover, display gaps and text flags. Keep the existing badge honest for failed, passed and absent rule results. Keep the existing three groups, move details, filters, approval controls and export. Preserve the old seed's empty health and rule arrays and the Zod error state for malformed runs. **Done when** the generated seed passes engine and web checks, the page shows all three populated groups, the rule badge and store health, and observable checks confirm approvals, CSV export, keyboard focus and no horizontal overflow at 390 px. After landing and the separately authorized push, repeat the new feature checks on the public deployment without signing in.

- [x] **5. Repair independent approvals (F-01).** Budget cumulative receipts against snapshot headroom and cumulative outgoing moves against snapshot category display and donor style cover. Include existing in-transit but no pending recommendation in those budgets. Validate those limits independently, preserve the per-move approval workflow, and regenerate the seed. **Done when** the validator rejects plans whose capacity, display or donor cover only pass by netting pending moves, and the regenerated run and approval subsets from the finding pass all rules.

## Files / areas

- `engine/src/stock_mover/allocate.py`, `demand.py`, `constants.py` and new focused engine code for store moves and independent validation.
- `engine/src/stock_mover/run.py`, `cli.py`, and `engine/tests/`, including the existing real-pack and schema tests in `test_run.py`.
- `data/raw/` supplies the read-only source data, especially snapshot, rules, routes, min display and flagship protection.
- `apps/web/data/seed-run.json`, `apps/web/src/app/page.tsx`, and the existing approve components and formatting helpers. The Pydantic, JSON Schema and Zod shapes already cover this feature.

## Data / contracts

- Keep the wire shape and move types. Use `store_to_store` for store destinations and `pull_back` for store-to-WH-KOL. Distinguish ageing, rebalancing and capacity relief through the real reason. Use stable, unique IDs. Retain MRP value and the strict senior-approval threshold per recommendation. Use the existing MRP-based priority convention and stable sorting. Use receiving SKU numbers for deliveries and donor SKU numbers for pullbacks, with clear labels when the source matters.
- Use 31 Oct 2026 as the data reference date and preserve the CLI trigger and timestamp behavior. Use the same cleaned stock, combined accessory display category and forecast as the warehouse plan. In-transit counts toward projected store inventory, capacity and cover, and is unavailable to ship. Proposed incoming moves likewise do not become source supply in the same run. Maintain exact source limits, even when later recommendations touch the same SKU or store. Preserve legacy warehouse min-display top-ups when validating net need.
- Ageing means oldest receipt more than 180 days ago and SKU cover greater than 120 days. Use existing demand-history logic to distinguish genuine zero demand from thin exposure. For eligible old on-hand with genuine zero forecast, zero demand implies no consumption for the ageing check. Preserve the existing null representation for zero forecast in JSON.
- Store health describes the data snapshot. Use cleaned on-hand and in-transit component counts, sum them for fill versus capacity, and divide that available-plus-arriving stock total by aggregate store forecast for cover. Compute gaps against tier minimums using the shared category mapping. Use non-color text for flags and unavailable metrics. Render run strings as text.
- No live inventory or shared approval writes. The engine writes the results to the run file and the web server validates that file. The browser keeps decisions in the existing run-ID and move-ID localStorage scope.

## Testing

- All 81 engine tests passed with `uv run pytest -q` in `engine/`.
- After implementation, rerun `uv run pytest -q`. In `apps/web` run `pnpm lint`, `pnpm exec tsc --noEmit` and `pnpm build`. Regenerate the seed from `engine/` with `uv run stock-mover run --trigger seed --out ../apps/web/data/seed-run.json`.
- Cover zero stock, missing receipt age, insufficient supply or destination room, zero and thin demand, pre-existing display gaps, and multiple moves sharing source stock or destination headroom. Exercise both CLI failure and seeded page states through the normal entry points. There is no configured browser automation command. Capture manual page evidence during the check and deployment gates.

## Notes for the AI

- Use small pure engine functions and existing pandas/Pydantic types. Keep file I/O in the CLI and rendering in the existing Next.js flow. Compare raw quantities for rule checks before rounding display values.
- Retain the warm Dispatch layout, no Manyavar marks, visible focus and reduced motion behavior. Keep route metadata, reasons, approval and CSV semantics consistent with the existing page. Never publish a failing seed.
- Complete and push only with existing workflow authorization and before 4:45 pm IST on 21 Nov 2026.

## Approved product decisions

- Use the oldest receipt as a SKU-level ageing signal and cap recommendations at eligible on-hand.
- Flag a store as under-stocked when any display gap exists or when both store velocity exceeds its tier median and store fill falls below its tier median.
- Use the reverse of the WH-KOL outbound route for the originating store's zone to estimate pullback lead time.
- Surface unavoidable pre-existing over-capacity in store health and forbid receipts that leave that store above capacity.

## Implementation verification

- The repaired seed contains 810 warehouse moves, 198 store transfers and 908 pullbacks. Ten rules passed. JKT-08 and IW-08 both appear in ageing moves.
- `uv run pytest -q` passed 108 tests. The new fixtures reject plans that rely on offsetting moves for capacity, display or donor cover. Both real approval cases from F-01 pass on the repaired run. Web lint, typecheck and production build passed again.
- Blueprint check exercised the approval interface before the engine-only repair. At 390 px the document did not overflow. The approval button had visible focus and accepted Enter. Decisions survived reload and the actual CSV download contained the approved transfer and excluded the rejected move.
- F-01 awaits re-audit. Public deployment evidence follows landing.

## Try it now

Run or do:

From `apps/web`, run `pnpm dev`, open `http://localhost:3000/`, and expand **Store health** above the approval queue.

Expected:

The rule badge reads **10 of 10 rules passed**. The strip shows 20 stores, and MZF-01 is marked under-stocked with a Mojari gap of 3.

This proves:

The validated seed feeds both the rule badge and the store health display.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":11755,"specSha256":"a6fae67ab770507a48d15c1538bf2008a330a5c96a36621f2dabfacce7c41c0d","branch":"refs/heads/feature/store-store-ageing-pull-back-rule-validator","head":"969faba440b69ba558f514aa7b3fd9a16eba4bfa","baseRef":"refs/heads/main","baseCommit":"969faba440b69ba558f514aa7b3fd9a16eba4bfa","sourceTree":"9b131f758630f01648eb3111016260b61fad86b4","landing":"local-merge","absentOptional":[]} -->

## Findings

### 5/F-01 [P1] closed - Approved moves can violate capacity and donor rules

**File:** engine/src/stock_mover/store_moves.py:79
**Found:** 2026-11-21 by /audit (scope: current; lens: quality, tests)
**Why it matters:** The planner spends headroom freed by other recommendations and credits incoming recommendations toward donor display and cover. The validator nets those same recommendations across the full plan. The approve page allows the merchandiser to export any subset. On the real pack, approving the warehouse group and the two-unit `s2s-KNP-01-LKO-01-SHW-03-L` transfer sends LKO-01 to 1,202 against capacity of 1,200. Approving only `age-BLR-04-BLR-02-IW-01-XXL` leaves BLR-04 with six IW-01 units against 11.30 required for 30 days of cover. Both examples fail the corresponding existing validator rule.
**Suggested fix:** Keep independent approvals by budgeting total receipts against snapshot headroom and cumulative donations against snapshot display and cover, including existing in-transit. Never use another pending recommendation to make a move eligible. Validate the independent limits and cover both real approval scenarios with regression tests.
**Resolution:** Re-audited on 2026-11-21. The planner and validator enforce separate receipt and outbound budgets against the snapshot plus existing in-transit. A fresh run matched the 1,916-move seed. Recomputing the budgets separately confirmed all 20 receiving stores, 93 donor categories, and 133 donor styles stay within the limits. LKO-01 receives exactly its 266 units of headroom and BLR-04 has no IW-01 store-to-store donations. All 108 engine tests passed, including the regression fixtures.
