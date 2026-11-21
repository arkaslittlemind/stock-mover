from dataclasses import replace
from datetime import date, timedelta

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
from stock_mover.loader import load_data
from stock_mover.store_moves import StorePlan, plan_store_moves
from stock_mover.validate import validate_moves

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


@pytest.fixture(scope="module")
def store_move_case():
    data = load_data()

    def make_case(sku_rows, store_rows, supply=None, minimums=NO_MIN, protected=(), ages=()):
        locations = pd.DataFrame(
            store_rows, columns=["store_id", "tier", "zone", "city", "stock_capacity_units"],
        )
        table = targets(skus(sku_rows))
        items = table[["sku_id", "style_id", "category", "size"]].drop_duplicates()
        items = items.assign(style_name="Test style", mrp=5_000)
        receipts = {(store, sku): TODAY - timedelta(days=age) for store, sku, age in ages}
        snapshot = [
            (row.store_id, row.sku_id, row.on_hand, row.in_transit, receipts.get((row.store_id, row.sku_id)))
            for row in table.itertuples(index=False)
        ]
        snapshot.extend(("WH-KOL", sku, units, 0, None) for sku, units in (supply or {}).items())
        fixture = replace(
            data, stores=locations, items=items, min_display=minimums,
            flagship_protected=pd.DataFrame(protected, columns=["store_id", "style_id"]),
            stock_snapshot=pd.DataFrame(
                snapshot, columns=["location_id", "sku_id", "on_hand", "in_transit", "oldest_stock_received_on"],
            ),
        )
        warehouse = allocate(table, supply or {}, store_headroom(table, locations), minimums)
        return table, warehouse, fixture

    return make_case


@pytest.fixture(scope="module")
def store_move_fixture(store_move_case):
    def plan(*args, **kwargs):
        table, warehouse, fixture = store_move_case(*args, **kwargs)
        return plan_store_moves(table, warehouse, fixture, TODAY, [])

    return plan


def test_rebalancing_uses_nearest_eligible_stores_after_warehouse(store_move_fixture):
    fixture = [
        ("D", "A", "North", "Local", 34),
        ("FLAG", "S++", "North", "Local", 100),
        ("Z-SAME", "A", "North", "Local", 100),
        ("A-ZONE", "A", "North", "Other", 100),
        ("A-FAR", "A", "East", "Far", 100),
    ]
    rows = [
        ("D", "K-1-M", "Kurta Set", "A", 1.0, 1, 20),
        ("FLAG", "K-1-M", "Kurta Set", "S++", 0.0, 40, 0),
        ("Z-SAME", "K-1-M", "Kurta Set", "A", 0.0, 3, 0),
        ("A-ZONE", "K-1-M", "Kurta Set", "A", 0.0, 2, 0),
        ("A-FAR", "K-1-M", "Kurta Set", "A", 0.0, 40, 0),
    ]
    moves = store_move_fixture(rows, fixture, {"K-1-M": 5}, protected=[("FLAG", "K-1")])
    assert [(m.from_location, m.units, m.lead_days) for m in moves] == [
        ("Z-SAME", 3, 2), ("A-ZONE", 2, 4), ("A-FAR", 3, 7),
    ]
    assert moves[0].numbers.cover_before == 26
    assert moves[-1].numbers.cover_after == 34


@pytest.mark.parametrize(
    ("source_units", "arriving", "other_sizes", "minimum", "expected"),
    [
        (5, 30, [], 0, [3, 2]),  # Only original on-hand may leave.
        (10, 0, [], 5, [3, 2]),  # Category stock remains at the display floor.
        # Donor style has 47 units and forecasts 1.4/day across three sizes.
        (15, 0, [("K-1-L", 0.2, 15), ("K-1-S", 1.0, 17)], 0, [3, 2]),
    ],
)
def test_rebalancing_shares_donor_limits_across_recipients(
    store_move_fixture, source_units, arriving, other_sizes, minimum, expected,
):
    locations = [
        ("D1", "A", "North", "Local", 3),
        ("D2", "A", "North", "Local", 100),
        ("S", "A", "North", "Local", 100),
    ]
    rate = 0.2 if other_sizes else 0.0
    rows = [
        ("D1", "K-1-M", "Kurta Set", "A", 1.0, 0, 0),
        ("D2", "K-1-M", "Kurta Set", "A", 1.0, 0, 0),
        ("S", "K-1-M", "Kurta Set", "A", rate, source_units, arriving),
    ]
    rows += [("S", sku, "Kurta Set", "A", forecast, units, 0) for sku, forecast, units in other_sizes]
    moves = store_move_fixture(rows, locations, minimums=min_display([("A", "Kurta Set", minimum)]))
    assert [(m.to_location, m.units) for m in moves] == list(zip(["D1", "D2"], expected))


@pytest.mark.parametrize(
    ("age", "on_hand", "rate", "expected"),
    [(180, 121, 1.0, 0), (181, 120, 1.0, 0), (181, 121, 1.0, 121), (181, 10, 0.0, 10)],
)
def test_ageing_thresholds_and_zero_demand_pullback(store_move_fixture, age, on_hand, rate, expected):
    moves = store_move_fixture(
        [("S", "K-1-M", "Kurta Set", "A", rate, on_hand, 0)],
        [("S", "A", "North", "Local", 200)],
        ages=[("S", "K-1-M", age)],
    )
    assert sum(m.units for m in moves) == expected
    assert all(m.type == "pull_back" and m.to_location == "WH-KOL" and m.lead_days == 4 for m in moves)


def test_ageing_goes_to_fastest_seller_with_headroom(store_move_fixture):
    locations = [
        ("S", "A", "North", "Local", 100),
        ("FULL", "A", "North", "Local", 100),
        ("FAST", "A", "East", "Far", 100),
        ("NEAR", "A", "North", "Local", 100),
    ]
    rows = [
        ("S", "K-1-M", "Kurta Set", "A", 0.0, 7, 0),
        ("FULL", "K-1-M", "Kurta Set", "A", 2.0, 94, 6),
        ("FAST", "K-1-M", "Kurta Set", "A", 1.5, 90, 6),
        ("NEAR", "K-1-M", "Kurta Set", "A", 1.0, 75, 5),
    ]
    moves = store_move_fixture(rows, locations, ages=[("S", "K-1-M", 181)])
    assert [(m.to_location, m.units, m.lead_days) for m in moves] == [
        ("FAST", 4, 7), ("NEAR", 3, 2),
    ]
    assert all(m.id.startswith("age-") and m.type == "store_to_store" for m in moves)


def test_ageing_does_not_swap_same_sku_between_stores(store_move_fixture):
    locations = [("A", "A", "North", "Local", 100), ("B", "A", "North", "Local", 100)]
    rows = [
        ("A", "K-1-M", "Kurta Set", "A", 0.0, 10, 0),
        ("B", "K-1-M", "Kurta Set", "A", 0.0, 10, 0),
        ("A", "K-1-L", "Kurta Set", "A", 0.1, 10, 0),
        ("B", "K-1-L", "Kurta Set", "A", 0.1, 10, 0),
    ]
    moves = store_move_fixture(rows, locations, ages=[("A", "K-1-M", 181), ("B", "K-1-M", 181)])
    assert [(m.from_location, m.to_location, m.units) for m in moves] == [
        ("A", "B", 10), ("B", "WH-KOL", 10),
    ]


def test_capacity_relief_uses_slowest_unprotected_stock_first(store_move_fixture):
    locations = [("S", "S++", "North", "Local", 20)]
    rows = [
        ("S", "K-1-M", "Kurta Set", "S++", 0.0, 10, 0),
        ("S", "K-2-M", "Kurta Set", "S++", 0.5, 3, 0),
        ("S", "K-3-M", "Kurta Set", "S++", 1.0, 12, 2),
    ]
    moves = store_move_fixture(rows, locations, protected=[("S", "K-1")])
    assert [(m.sku_id, m.units) for m in moves] == [("K-2-M", 3), ("K-3-M", 4)]
    assert all(m.id.startswith("capacity-") and m.type == "pull_back" for m in moves)


def test_pending_departure_cannot_make_room_for_ageing_receipt(store_move_case):
    rows = [
        ("A", "K-1-M", "Kurta Set", "A", 0.0, 9, 1),
        ("A", "K-2-M", "Kurta Set", "A", 0.01, 0, 0),
        ("B", "K-2-M", "Kurta Set", "A", 0.0, 1, 0),
        ("C", "K-1-M", "Kurta Set", "A", 0.1, 0, 0),
    ]
    stores = [("A", "A", "North", "Local", 10), ("B", "A", "North", "Local", 100),
              ("C", "A", "North", "Local", 100)]
    table, warehouse, ds = store_move_case(rows, stores, {"K-2-M": 0}, ages=[("B", "K-2-M", 181)])
    moves = plan_store_moves(table, warehouse, ds, TODAY, [])
    assert [(m.from_location, m.to_location) for m in moves] == [("A", "C"), ("B", "WH-KOL")]

    unsafe = StorePlan(table, warehouse, ds, TODAY, [])
    unsafe.rebalance()
    unsafe.record("age", "B", "A", "K-2-M", 1, "Fixture for a receipt relying on a departure.")
    failures = {rule.rule for rule in validate_moves(unsafe.moves, table, ds, [], TODAY) if not rule.passed}
    assert failures == {"capacity"}


@pytest.mark.parametrize("rule", ["minimum_display", "donor_cover"])
def test_pending_receipt_cannot_fund_donor_limits(store_move_case, rule):
    display_only = rule == "minimum_display"
    incoming_sku = "K-2-L" if display_only else "K-1-L"
    rows = [
        ("S", "K-1-M", "Kurta Set", "A", 0.0, 3, 0),
        ("S", incoming_sku, "Kurta Set", "A", 0.2, 0, 0),
        ("D", "K-1-M", "Kurta Set", "A", 0.1, 5, 0),
    ]
    stores = [("S", "A", "North", "Local", 100), ("D", "A", "North", "Local", 100)]
    minimums = min_display([("A", "Kurta Set", 3)]) if display_only else NO_MIN
    table, warehouse, ds = store_move_case(
        rows, stores, {incoming_sku: 4}, minimums=minimums, ages=[("S", "K-1-M", 181)],
    )
    moves = plan_store_moves(table, warehouse, ds, TODAY, [])
    assert all(m.to_location == "WH-KOL" for m in moves)
    assert len(moves) == (0 if display_only else 1)

    unsafe = StorePlan(table, warehouse, ds, TODAY, [])
    destination = "WH-KOL" if display_only else "D"
    unsafe.record("age", "S", destination, "K-1-M", 1, "Fixture for a donor relying on a receipt.")
    combined = warehouse_moves(table, warehouse, ds.items, ds.min_display, TODAY) + unsafe.moves
    failures = {result.rule for result in validate_moves(combined, table, ds, [], TODAY) if not result.passed}
    assert failures == {rule}


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
