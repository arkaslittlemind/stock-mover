import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import jsonschema
import pytest

from stock_mover.allocate import (
    add_targets, allocate, display_category, store_headroom, warehouse_lead_days, warehouse_supply,
)
from stock_mover.checks import find_data_issues
from stock_mover.cli import main
from stock_mover.constants import SCHEMA_PATH, SEED_RUN_PATH, TODAY
from stock_mover.contract import DataIssue, RuleResult, Run
from stock_mover.demand import build_demand
from stock_mover.health import store_health
from stock_mover.loader import load_data
from stock_mover.run import build_run, format_inr, run_text
from stock_mover.validate import validate_moves

NOW = datetime(2026, 11, 21, 6, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))


@pytest.fixture(scope="module")
def ds():
    return load_data()


@pytest.fixture(scope="module")
def run(ds):
    return build_run(ds, NOW, "manual")


@pytest.fixture(scope="module")
def parts(ds):
    issues = find_data_issues(ds)
    demand = build_demand(ds, issues, TODAY)
    table = add_targets(demand.skus, warehouse_lead_days(ds.stores, ds.lead_times))
    supply = warehouse_supply(ds.stock_snapshot, issues)
    alloc = allocate(table, supply, store_headroom(demand.skus, ds.stores), ds.min_display)
    return table, supply, alloc


@pytest.fixture(scope="module")
def schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_run_validates_against_schema_and_contract(run, schema):
    data = json.loads(run_text(run))
    jsonschema.validate(data, schema)
    assert Run.model_validate(data) == run
    assert data["run"]["id"] == "2026-10-31-20261121T003000Z"
    assert data["run"]["trigger"] == "manual"
    assert data["moves"] and all("from" in m and "to" in m for m in data["moves"])


def test_naive_now_is_rejected(ds):
    with pytest.raises(ValueError):
        build_run(ds, datetime(2026, 11, 21), "manual")


def test_every_move_is_consistent(run):
    ids = [m.id for m in run.moves]
    assert len(ids) == len(set(ids))
    for m in run.moves:
        assert m.from_location != m.to_location
        assert (m.from_location == "WH-KOL") == (m.type == "warehouse_to_store")
        assert (m.to_location == "WH-KOL") == (m.type == "pull_back")
        assert m.units >= 1
        assert m.needs_senior_approval == (m.value_mrp > 100_000)
        assert m.arrives_on == TODAY + timedelta(days=m.lead_days)
    assert [m.priority for m in run.moves] == sorted((m.priority for m in run.moves), reverse=True)


def test_real_run_has_valid_moves_of_all_types_and_store_health(run, ds):
    assert {m.type for m in run.moves} == {"warehouse_to_store", "store_to_store", "pull_back"}
    assert {m.style_id for m in run.moves if m.id.startswith("age-")} >= {"JKT-08", "IW-08"}
    assert run.rule_check and all(r.passed and not r.failures for r in run.rule_check)
    flagship_stores = set(ds.stores.loc[ds.stores["tier"] == "S++", "store_id"])
    protected = set(zip(ds.flagship_protected["store_id"], ds.flagship_protected["style_id"]))
    assert not any(
        (m.from_location, m.style_id) in protected and m.from_location in flagship_stores
        for m in run.moves
    )
    assert {store.store_id for store in run.stores} == set(ds.stores["store_id"])
    health = {store.store_id: store for store in run.stores}
    assert "under_stocked" in health["MZF-01"].flags
    assert any(gap.category == "Mojari" and gap.gap == 3 for gap in health["MZF-01"].min_display_gaps)
    assert health["KNP-03"].fill_pct < 100


def test_real_approval_subsets_do_not_need_offsetting_moves(run, parts, ds):
    warehouse = [move for move in run.moves if move.type == "warehouse_to_store"]
    store_outbound = [move for move in run.moves if move.type != "warehouse_to_store"]
    lko_receipts = [move for move in store_outbound if move.to_location == "LKO-01"]
    assert sum(move.units for move in warehouse if move.to_location == "LKO-01") == 266
    assert not lko_receipts
    assert not any(
        move.type == "store_to_store" and move.from_location == "BLR-04" and move.style_id == "IW-01"
        for move in store_outbound
    )
    issues = find_data_issues(ds)
    for subset in (warehouse + lko_receipts, store_outbound):
        assert all(result.passed for result in validate_moves(subset, parts[0], ds, issues, TODAY))


def test_no_move_touches_a_data_issue_pair(run):
    pairs = {(i.location_id, i.sku_id) for i in run.data_issues}
    assert pairs == {("KNP-03", "SHW-02-L"), ("MYS-02", "KUR-02-M")}
    assert not any((m.to_location, m.sku_id) in pairs or (m.from_location, m.sku_id) in pairs for m in run.moves)


def test_never_exceeds_warehouse_stock_or_capacity(parts):
    table, supply, alloc = parts
    for sku, units in supply.items():
        assert sum(u for (_, s), u in alloc.units.items() if s == sku) <= units
    assert all(room >= 0 for room in alloc.headroom_left.values())


def test_never_resends_in_transit(parts):
    table, _, alloc = parts
    fair = {k: u - alloc.min_display_units.get(k, 0) for k, u in alloc.units.items()}
    need = {(s, k): n for s, k, n in zip(table["store_id"], table["sku_id"], table["need"])}
    # Fair-share units never exceed target - (on hand + in transit).
    assert all(u <= max(need[k], 0) for k, u in fair.items() if u > 0)


def test_kur01_warehouse_units_go_to_lowest_cover(parts):
    table, supply, alloc = parts
    kur01 = [s for s in supply if s.startswith("KUR-01-")]
    assert sum(supply[s] for s in kur01) == 50
    assert sum(u for (_, s), u in alloc.units.items() if s in kur01) == 50
    rows = table[table["sku_id"].isin(kur01)]
    for sku in kur01:
        sku_rows = rows[rows["sku_id"] == sku]
        given = [c for (st, s), c in alloc.last_unit_cover.items() if s == sku]
        if not given:
            continue
        worst_given = max(given)
        for r in sku_rows.itertuples():
            got = alloc.units.get((r.store_id, sku), 0)
            if r.need > got and alloc.headroom_left[r.store_id] > 0:
                final_cover = (r.on_hand + r.in_transit + got) / r.forecast_daily
                assert final_cover >= worst_given, (r.store_id, sku)


def test_mzf01_gets_mojari_min_display_top_up(run):
    mzf = [m for m in run.moves if m.to_location == "MZF-01" and m.category == "Mojari"]
    assert any("5 Mojari on display vs a minimum of 8" in m.reason for m in mzf)


def test_blr05_gets_min_display_top_up(run):
    assert any(m.to_location == "BLR-05" and "on display vs a minimum of" in m.reason for m in run.moves)


def test_lko01_gets_kur04(run):
    kur04 = [m for m in run.moves if m.to_location == "LKO-01" and m.style_id == "KUR-04"]
    assert sum(m.units for m in kur04) > 0


def test_format_inr():
    assert format_inr(11_393_257) == "1,13,93,257"
    assert format_inr(100_000) == "1,00,000"
    assert format_inr(999) == "999"


def test_seed_run_file_is_valid(schema):
    data = json.loads(SEED_RUN_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(data, schema)
    assert Run.model_validate(data).run.trigger == "seed"


def assert_rule_failed(rule, moves, table, ds, issues=()):
    results = {result.rule: result for result in validate_moves(moves, table, ds, list(issues), TODAY)}
    assert results[rule].checked > 0
    assert not results[rule].passed
    assert results[rule].failures


@pytest.mark.parametrize(
    ("rule", "mutate"),
    [
        ("senior_approval", lambda m: {"needs_senior_approval": not m.needs_senior_approval}),
        ("move_details", lambda m: {"lead_days": m.lead_days + 1}),
        ("ageing", lambda m: {"id": f"age-{m.id}"}),
    ],
)
def test_validator_rejects_incorrect_move_fields(rule, mutate, run, parts, ds):
    move = next(m for m in run.moves if m.type == "warehouse_to_store")
    assert_rule_failed(rule, [move.model_copy(update=mutate(move))], parts[0], ds)


def test_validator_rejects_excluded_destination(run, parts, ds):
    move = next(m for m in run.moves if m.type == "warehouse_to_store")
    issue = DataIssue(location_id=move.to_location, sku_id=move.sku_id,
                      checks=["negative_stock"], note="Excluded", excluded=True)
    assert_rule_failed("excluded_pairs", [move], parts[0], ds, [issue])


def test_validator_rejects_cumulative_source_overspend(run, parts, ds):
    table, supply, _ = parts
    move = next(m for m in run.moves if m.type == "warehouse_to_store" and supply[m.sku_id] >= 2)
    units = supply[move.sku_id] // 2 + 1
    mrp = int(ds.items.set_index("sku_id").at[move.sku_id, "mrp"])
    value = units * mrp
    first = move.model_copy(update={"units": units, "value_mrp": value, "needs_senior_approval": value > 100_000})
    second = first.model_copy(update={"id": f"{first.id}-second"})
    assert_rule_failed("source_stock", [first, second], table, ds)


def test_validator_rejects_store_receipts_over_capacity(run, parts, ds):
    move = next(m for m in run.moves if m.type == "warehouse_to_store")
    table = parts[0]
    rows = table.loc[table["store_id"] == move.to_location]
    fill = int(rows["on_hand"].sum() + rows["in_transit"].sum())
    stores = ds.stores.copy()
    stores.loc[stores["store_id"] == move.to_location, "stock_capacity_units"] = fill - 1
    constrained = replace(ds, stores=stores)
    assert_rule_failed("capacity", [move], table, constrained)
    assert all(r.passed for r in validate_moves([], table, constrained, [], TODAY))
    health = {store.store_id: store for store in store_health(table, constrained, [])}
    assert "over_capacity" in health[move.to_location].flags


def test_validator_rejects_replenishment_of_units_already_in_transit(run, parts, ds):
    move = next(m for m in run.moves if m.id.startswith("s2s-"))
    table = parts[0].copy()
    destination = (table["store_id"] == move.to_location) & (table["sku_id"] == move.sku_id)
    table.loc[destination, "in_transit"] += table.loc[destination, "need"]
    table.loc[destination, "need"] = 0
    assert_rule_failed("in_transit", [move], table, ds)


def test_validator_rejects_protected_style_leave(run, parts, ds):
    move = next(m for m in run.moves if m.from_location != "WH-KOL")
    stores = ds.stores.copy()
    stores.loc[stores["store_id"] == move.from_location, "tier"] = "S++"
    protected = ds.flagship_protected.copy()
    protected.loc[len(protected)] = [move.from_location, 1, move.style_id]
    assert_rule_failed("flagship_protection", [move], parts[0], replace(ds, stores=stores, flagship_protected=protected))


def test_validator_rejects_donor_category_below_display_minimum(run, parts, ds):
    move = next(m for m in run.moves if m.from_location != "WH-KOL")
    table = parts[0]
    tier = ds.stores.set_index("store_id").at[move.from_location, "tier"]
    category = display_category(move.category)
    source = table.loc[(table["store_id"] == move.from_location) & (table["category"].map(display_category) == category)]
    minimum = int(source["on_hand"].sum() + source["in_transit"].sum())
    minimums = ds.min_display.copy()
    key = (minimums["tier"] == tier) & (minimums["category"] == category)
    if key.any():
        minimums.loc[key, "min_display_units"] = minimum
    else:
        minimums.loc[len(minimums), ["tier", "category", "min_display_units"]] = [tier, category, minimum]
    assert_rule_failed("minimum_display", [move], table, replace(ds, min_display=minimums))


def test_validator_rejects_insufficient_donor_style_cover(run, parts, ds):
    move = next(m for m in run.moves if m.type == "store_to_store")
    table = parts[0].copy()
    source_style = (table["store_id"] == move.from_location) & (table["style_id"] == move.style_id)
    table.loc[source_style, "forecast_daily"] = table.loc[source_style, "on_hand"] + 1.0
    assert_rule_failed("donor_cover", [move], table, ds)


def test_failed_validation_leaves_previous_output(monkeypatch, tmp_path, capsys):
    failure = RuleResult(rule="capacity", label="Store capacity", checked=1, passed=False, failures=["Too full."])
    monkeypatch.setattr("stock_mover.run.validate_moves", lambda *_args: [failure])
    previous = tmp_path / "run.json"
    previous.write_text("previous run", encoding="utf-8")
    with pytest.raises(SystemExit) as rejected:
        main(["run", "--out", str(previous)])
    assert rejected.value.code == 1
    assert "Store capacity: Too full." in capsys.readouterr().err
    assert previous.read_text(encoding="utf-8") == "previous run"
