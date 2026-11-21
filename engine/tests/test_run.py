import json
from datetime import datetime, timedelta, timezone

import jsonschema
import pytest

from stock_mover.allocate import add_targets, allocate, store_headroom, warehouse_lead_days, warehouse_supply
from stock_mover.checks import find_data_issues
from stock_mover.constants import SCHEMA_PATH, SEED_RUN_PATH, TODAY
from stock_mover.contract import Run
from stock_mover.demand import build_demand
from stock_mover.loader import load_data
from stock_mover.run import build_run, format_inr, run_text

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
        assert m.type == "warehouse_to_store" and m.from_location == "WH-KOL"
        assert m.units >= 1
        assert m.needs_senior_approval == (m.value_mrp > 100_000)
        assert m.arrives_on == TODAY + timedelta(days=m.lead_days)
    assert [m.priority for m in run.moves] == sorted((m.priority for m in run.moves), reverse=True)


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
