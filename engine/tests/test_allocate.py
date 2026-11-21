from datetime import date

import pandas as pd
import pytest

from stock_mover.allocate import (
    add_targets,
    allocate,
    store_headroom,
    warehouse_lead_days,
    warehouse_moves,
    warehouse_supply,
)
from stock_mover.contract import DataIssue

TODAY = date(2026, 10, 31)


# ---------- fixture builders ----------

def stores(rows):
    """rows: (store_id, tier, zone, capacity)."""
    return pd.DataFrame(rows, columns=["store_id", "tier", "zone", "stock_capacity_units"])


LEAD_TIMES = pd.DataFrame(
    [
        ("Warehouse WH-KOL to store, East zone (Bihar)", 3),
        ("Warehouse WH-KOL to store, North zone (UP)", 4),
        ("Store to store, same city", 2),
    ],
    columns=["route", "days"],
)


def skus(rows):
    """rows: (store_id, sku_id, category, tier, forecast, on_hand, in_transit)."""
    t = pd.DataFrame(
        rows, columns=["store_id", "sku_id", "category", "tier", "forecast_daily", "on_hand", "in_transit"]
    )
    t["style_id"] = t["sku_id"].str.rsplit("-", n=1).str[0]
    t["size"] = t["sku_id"].str.rsplit("-", n=1).str[1]
    t["zone"] = "North"
    t["units_84"] = 0
    t["days_in_stock_84"] = 84
    t["velocity"] = t["forecast_daily"]
    t["velocity_source"] = "own"
    t["lift"] = 1.0
    t["cover_days"] = None
    return t


def min_display(rows):
    return pd.DataFrame(rows, columns=["tier", "category", "min_display_units"])


NO_MIN = min_display([])


def targets(table, lead=4):
    return add_targets(table, {s: lead for s in table["store_id"].unique()})


def issue(loc, sku):
    return DataIssue(location_id=loc, sku_id=sku, checks=["negative_stock"], note="x", excluded=True)


# ---------- step 1: targets, needs, supply, headroom ----------

def test_lead_days_by_zone():
    s = stores([("LKO-01", "S++", "North", 100), ("PAT-01", "A", "East", 100)])
    assert warehouse_lead_days(s, LEAD_TIMES) == {"LKO-01": 4, "PAT-01": 3}


def test_unknown_zone_raises():
    s = stores([("BLR-01", "A", "South", 100)])
    with pytest.raises(ValueError, match="South"):
        warehouse_lead_days(s, LEAD_TIMES)


def test_in_transit_covering_target_means_no_need():
    # forecast 1/day x (4 + 30) = 34 target; 10 on hand + 24 in transit already cover it.
    t = targets(skus([("S1", "K-1-M", "Kurta Set", "A", 1.0, 10, 24)]))
    assert t.loc[0, "target"] == 34
    assert t.loc[0, "need"] == 0


def test_need_is_target_minus_stock_and_in_transit():
    t = targets(skus([("S1", "K-1-M", "Kurta Set", "A", 1.0, 10, 4)]))
    assert t.loc[0, "need"] == 20


def test_zero_forecast_has_zero_target():
    t = targets(skus([("S1", "K-1-M", "Kurta Set", "A", 0.0, 0, 0)]))
    assert t.loc[0, "target"] == 0 and t.loc[0, "need"] == 0


def test_target_rounds_half_up():
    # 0.25 x 34 = 8.5 -> 9 (Python round would give 8).
    t = targets(skus([("S1", "K-1-M", "Kurta Set", "A", 0.25, 0, 0)]))
    assert t.loc[0, "target"] == 9


def test_supply_is_warehouse_on_hand_without_excluded_pairs():
    snap = pd.DataFrame(
        [("WH-KOL", "A-1", 5, 0), ("WH-KOL", "B-1", 7, 0), ("WH-KOL", "C-1", 0, 0), ("S1", "A-1", 9, 0)],
        columns=["location_id", "sku_id", "on_hand", "in_transit"],
    )
    assert warehouse_supply(snap, [issue("WH-KOL", "B-1")]) == {"A-1": 5}


def test_headroom_uses_demand_table_and_is_never_negative():
    # The demand table has already dropped excluded rows, so they never count.
    s = stores([("S1", "A", "North", 50), ("S2", "A", "North", 10)])
    t = skus([("S1", "K-1-M", "Kurta Set", "A", 1.0, 30, 5), ("S2", "K-1-M", "Kurta Set", "A", 1.0, 12, 0)])
    assert store_headroom(t, s) == {"S1": 15, "S2": 0}


# ---------- step 2: allocation ----------

def test_scarce_units_go_to_lowest_cover_first():
    t = targets(skus([
        ("S1", "K-1-M", "Kurta Set", "A", 1.0, 20, 0),  # cover 20
        ("S2", "K-1-M", "Kurta Set", "A", 1.0, 2, 0),   # cover 2
        ("S3", "K-1-M", "Kurta Set", "A", 1.0, 5, 0),   # cover 5
    ]))
    alloc = allocate(t, {"K-1-M": 5}, {"S1": 99, "S2": 99, "S3": 99}, NO_MIN)
    # S2 fills from 2 up to 5, then S2 and S3 alternate: 3 + 1 to S2/S3 ... S1 gets nothing.
    assert alloc.units.get(("S1", "K-1-M"), 0) == 0
    assert alloc.units[("S2", "K-1-M")] + alloc.units[("S3", "K-1-M")] == 5
    assert alloc.units[("S2", "K-1-M")] == 4


def test_two_units_go_to_the_two_lowest_cover_stores():
    t = targets(skus([
        ("S1", "K-1-M", "Kurta Set", "A", 1.0, 9, 0),
        ("S2", "K-1-M", "Kurta Set", "A", 1.0, 1, 0),
        ("S3", "K-1-M", "Kurta Set", "A", 2.0, 4, 0),  # cover 2
    ]))
    alloc = allocate(t, {"K-1-M": 2}, {"S1": 99, "S2": 99, "S3": 99}, NO_MIN)
    assert alloc.units == {("S2", "K-1-M"): 1, ("S3", "K-1-M"): 1}


def test_never_exceeds_supply_or_headroom():
    rows = [(f"S{i}", sku, "Kurta Set", "A", 3.0, 0, 0) for i in range(4) for sku in ("K-1-M", "K-1-L")]
    t = targets(skus(rows))
    headroom = {"S0": 5, "S1": 0, "S2": 40, "S3": 200}
    supply = {"K-1-M": 60, "K-1-L": 13}
    alloc = allocate(t, supply, headroom, NO_MIN)
    for sku, units in supply.items():
        assert sum(u for (_, s), u in alloc.units.items() if s == sku) <= units
    for store, room in headroom.items():
        assert sum(u for (s, _), u in alloc.units.items() if s == store) <= room
    assert not any(s == "S1" for s, _ in alloc.units)
    assert alloc.units[("S0", "K-1-M")] + alloc.units[("S0", "K-1-L")] == 5


def test_need_is_never_exceeded_by_fair_share():
    t = targets(skus([("S1", "K-1-M", "Kurta Set", "A", 1.0, 30, 0)]))  # need 4
    alloc = allocate(t, {"K-1-M": 100}, {"S1": 100}, NO_MIN)
    assert alloc.units == {("S1", "K-1-M"): 4}


def test_min_display_gap_filled_without_forecast():
    t = targets(skus([
        ("S1", "M-1-8", "Mojari", "A", 0.0, 2, 0),
        ("S1", "M-1-9", "Mojari", "A", 0.0, 0, 0),
        ("S1", "M-2-8", "Mojari", "A", 0.0, 1, 0),
    ]))
    md = min_display([("A", "Mojari", 8)])
    alloc = allocate(t, {"M-1-8": 10, "M-1-9": 10, "M-2-8": 10}, {"S1": 100}, md)
    assert sum(alloc.units.values()) == 5
    assert alloc.min_display_units == alloc.units
    # Spread across SKUs: fewest units at the store first.
    assert alloc.units == {("S1", "M-1-8"): 1, ("S1", "M-1-9"): 3, ("S1", "M-2-8"): 1}


def test_min_display_groups_accessories():
    t = targets(skus([
        ("S1", "SAF-1-F", "Safa", "B", 0.0, 1, 0),
        ("S1", "MAL-1-F", "Mala", "B", 0.0, 1, 0),
        ("S1", "STO-1-F", "Stole", "B", 0.0, 1, 0),
    ]))
    md = min_display([("B", "Accessories (Safa/Mala/Stole)", 4)])
    alloc = allocate(t, {"SAF-1-F": 5}, {"S1": 100}, md)
    assert alloc.units == {("S1", "SAF-1-F"): 1}


def test_min_display_units_count_toward_need():
    # need 4 by demand; gap of 6 to min display. Min display gives 6, fair share adds nothing.
    t = targets(skus([("S1", "K-1-M", "Kurta Set", "A", 1.0, 30, 0)]))
    md = min_display([("A", "Kurta Set", 36)])
    alloc = allocate(t, {"K-1-M": 100}, {"S1": 100}, md)
    assert alloc.units == {("S1", "K-1-M"): 6}


def test_store_at_capacity_gets_nothing():
    t = targets(skus([("S1", "K-1-M", "Kurta Set", "A", 5.0, 0, 0)]))
    md = min_display([("A", "Kurta Set", 10)])
    alloc = allocate(t, {"K-1-M": 100}, {"S1": 0}, md)
    assert alloc.units == {}


def test_allocation_is_deterministic():
    rows = [(f"S{i}", sku, "Kurta Set", "A", 1.0 + i % 2, i, 0) for i in range(6) for sku in ("K-1-M", "K-1-L")]
    t = targets(skus(rows))
    args = ({"K-1-M": 17, "K-1-L": 9}, {f"S{i}": 30 for i in range(6)}, NO_MIN)
    assert allocate(t, *args).units == allocate(t.sample(frac=1, random_state=1), *args).units


# ---------- step 3: moves ----------

ITEMS = pd.DataFrame(
    [("K-1-M", "K-1", "Ivory Kurta", "Kurta Set", "M", 60_000),
     ("M-1-8", "M-1", "Gold Mojari", "Mojari", "8", 2_000)],
    columns=["sku_id", "style_id", "style_name", "category", "size", "mrp"],
)


def test_moves_fill_the_contract():
    t = targets(skus([
        ("S1", "K-1-M", "Kurta Set", "A", 1.0, 4, 0),
        ("S2", "M-1-8", "Mojari", "A", 0.0, 3, 0),
    ]))
    md = min_display([("A", "Mojari", 5)])
    alloc = allocate(t, {"K-1-M": 2, "M-1-8": 9}, {"S1": 99, "S2": 99}, md)
    moves = {m.id: m for m in warehouse_moves(t, alloc, ITEMS, md, TODAY)}

    big = moves["w2s-S1-K-1-M"]
    assert (big.from_location, big.to_location, big.units) == ("WH-KOL", "S1", 2)
    assert big.value_mrp == 120_000 and big.needs_senior_approval
    assert big.priority == 120_000
    assert big.arrives_on == date(2026, 11, 4) and big.lead_days == 4
    assert big.numbers.cover_before == 4.0 and big.numbers.cover_after == 6.0
    assert big.reason.endswith("Send 2 from WH-KOL, arrives 4 Nov.")

    mojari = moves["w2s-S2-M-1-8"]
    assert mojari.units == 2 and not mojari.needs_senior_approval
    assert mojari.numbers.cover_before is None and mojari.numbers.cover_after is None
    assert "minimum of 5" in mojari.reason and "3 Mojari" in mojari.reason
    # Sorted by priority, highest first.
    assert [m.id for m in warehouse_moves(t, alloc, ITEMS, md, TODAY)][0] == "w2s-S1-K-1-M"


def test_reason_names_thin_history():
    t = skus([("S1", "K-1-M", "Kurta Set", "A", 2.0, 0, 0)])
    t["days_in_stock_84"] = 14
    t["units_84"] = 12
    t = targets(t)
    alloc = allocate(t, {"K-1-M": 3}, {"S1": 99}, NO_MIN)
    [move] = warehouse_moves(t, alloc, ITEMS, NO_MIN, TODAY)
    assert "in stock only 14 of 84 days and still sold 12" in move.reason
