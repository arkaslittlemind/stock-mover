from datetime import date, timedelta

import pandas as pd
import pytest

from stock_mover.checks import find_data_issues
from stock_mover.demand import (
    add_forecast_and_cover,
    apply_peer_velocity,
    base_table,
    build_demand,
    style_cover,
    zone_lift,
)
from stock_mover.loader import load_data

TODAY = date(2026, 10, 31)
OLD = date(2020, 1, 1)


# ---------- fixture builders ----------

def stores(rows):
    return pd.DataFrame(rows, columns=["store_id", "tier", "zone", "opened_on"])


def items(rows):
    return pd.DataFrame(rows, columns=["sku_id", "style_id", "category", "size", "launch_date"])


def sales(rows):
    """rows: (bill_date, store_id, sku_id, qty) -> (bills, bill_lines)."""
    bills = pd.DataFrame(
        [(f"B{i}", d, s) for i, (d, s, _, _) in enumerate(rows)],
        columns=["bill_id", "bill_date", "store_id"],
    )
    lines = pd.DataFrame(
        [(f"B{i}", sku, qty) for i, (_, _, sku, qty) in enumerate(rows)],
        columns=["bill_id", "sku_id", "qty"],
    )
    return bills, lines


def weekly(rows):
    """rows: (store_id, sku_id, total days in stock) spread as one row on TODAY's week."""
    return pd.DataFrame(
        [(TODAY, s, sku, d) for s, sku, d in rows],
        columns=["week_ending", "store_id", "sku_id", "days_in_stock"],
    )


def table_for(store_rows, item_rows, sale_rows, weekly_rows):
    bills, lines = sales(sale_rows)
    return base_table(stores(store_rows), items(item_rows), bills, lines, weekly(weekly_rows), TODAY)


def row(table, store, sku):
    return table[(table["store_id"] == store) & (table["sku_id"] == sku)].iloc[0]


ITEM_A = [("A-M", "A", "Kurta Set", "M", OLD)]


# ---------- step 1: own velocity ----------

def test_stock_out_masking_removed():
    t = table_for(
        [("S1", "A", "North", OLD)], ITEM_A,
        [(TODAY - timedelta(days=i), "S1", "A-M", 1) for i in range(14)],
        [("S1", "A-M", 14)],
    )
    r = row(t, "S1", "A-M")
    assert r["units_84"] == 14
    assert r["days_in_stock_84"] == 14
    assert r["own_velocity"] == pytest.approx(1.0)  # not 14 / 84


def test_sales_outside_window_ignored():
    t = table_for(
        [("S1", "A", "North", OLD)], ITEM_A,
        [(TODAY - timedelta(days=84), "S1", "A-M", 5), (TODAY - timedelta(days=83), "S1", "A-M", 2),
         (TODAY + timedelta(days=1), "S1", "A-M", 9)],
        [("S1", "A-M", 20)],
    )
    assert row(t, "S1", "A-M")["units_84"] == 2


def test_missing_rows_are_zero_and_every_store_sku_present():
    t = table_for(
        [("S1", "A", "North", OLD), ("S2", "A", "North", OLD)],
        ITEM_A + [("B-M", "B", "Kurta Set", "M", OLD)], [], [],
    )
    assert len(t) == 4
    assert (t["units_84"] == 0).all() and (t["days_in_stock_84"] == 0).all()
    assert (t["own_velocity"] == 0.0).all()


# ---------- step 2: peer velocity ----------

def peers_fixture(extra_stores=(), target_days=5, target_open=OLD, launch=OLD, zone_peer=True):
    store_rows = [("T", "A", "North", target_open), ("P_NET", "A", "South", OLD)]
    if zone_peer:
        store_rows.append(("P_ZONE", "A", "North", OLD))
    store_rows += list(extra_stores)
    item_rows = [("A-M", "A", "Kurta Set", "M", launch)]
    sale_rows = []
    weekly_rows = [("T", "A-M", target_days), ("P_NET", "A-M", 40)]
    # P_NET: 40 units over 40 days -> 1.0/day; P_ZONE: 20 units over 40 days -> 0.5/day.
    sale_rows += [(TODAY - timedelta(days=i % 40), "P_NET", "A-M", 1) for i in range(40)]
    if zone_peer:
        weekly_rows.append(("P_ZONE", "A-M", 40))
        sale_rows += [(TODAY - timedelta(days=i), "P_ZONE", "A-M", 1) for i in range(20)]
    return table_for(store_rows, item_rows, sale_rows, weekly_rows)


def test_thin_history_uses_same_zone_peer_rate():
    t = apply_peer_velocity(peers_fixture(), TODAY)
    r = row(t, "T", "A-M")
    assert r["velocity_source"] == "peer_zone"
    assert r["velocity"] == pytest.approx(0.5)  # T has no sales, so scale = 1.0


def test_falls_back_to_network_peers():
    t = apply_peer_velocity(peers_fixture(zone_peer=False), TODAY)
    r = row(t, "T", "A-M")
    assert r["velocity_source"] == "peer_network"
    assert r["velocity"] == pytest.approx(1.0)


def test_other_tier_is_never_a_peer():
    t = peers_fixture(zone_peer=False, extra_stores=[("B_ZONE", "B", "North", OLD)])
    t = apply_peer_velocity(t, TODAY)
    assert row(t, "T", "A-M")["velocity_source"] == "peer_network"


def test_new_store_uses_peers_despite_days_in_stock():
    t = apply_peer_velocity(peers_fixture(target_days=20, target_open=TODAY - timedelta(days=20)), TODAY)
    assert row(t, "T", "A-M")["velocity_source"] == "peer_zone"


def test_new_style_uses_peers_despite_days_in_stock():
    t = apply_peer_velocity(peers_fixture(target_days=20, launch=TODAY - timedelta(days=25)), TODAY)
    assert row(t, "T", "A-M")["velocity_source"] == "peer_zone"


def test_enough_history_keeps_own_velocity():
    t = apply_peer_velocity(peers_fixture(target_days=14), TODAY)
    r = row(t, "T", "A-M")
    assert r["velocity_source"] == "own"
    assert r["velocity"] == r["own_velocity"]


def test_peer_rate_scaled_by_store_rate():
    # T sells 42 units of another SKU over 84 days (0.5/day); P_ZONE's store rate is 20/84.
    store_rows = [("T", "A", "North", OLD), ("P_ZONE", "A", "North", OLD)]
    item_rows = [("A-M", "A", "Kurta Set", "M", OLD), ("X-M", "X", "Kurta Set", "M", OLD)]
    sale_rows = [(TODAY - timedelta(days=i), "P_ZONE", "A-M", 1) for i in range(20)]
    sale_rows += [(TODAY - timedelta(days=i), "T", "X-M", 1) for i in range(42)]
    weekly_rows = [("T", "A-M", 0), ("P_ZONE", "A-M", 40), ("T", "X-M", 84)]
    t = apply_peer_velocity(table_for(store_rows, item_rows, sale_rows, weekly_rows), TODAY)
    expected_scale = (42 / 84) / (20 / 84)
    assert row(t, "T", "A-M")["velocity"] == pytest.approx(0.5 * expected_scale)


def test_no_qualifying_peer_keeps_own_thin():
    t = table_for(
        [("T", "A", "North", OLD), ("P", "A", "North", OLD)], ITEM_A,
        [(TODAY, "T", "A-M", 3)], [("T", "A-M", 6), ("P", "A-M", 10)],
    )
    t = apply_peer_velocity(t, TODAY)
    r = row(t, "T", "A-M")
    assert r["velocity_source"] == "own_thin"
    assert r["velocity"] == pytest.approx(0.5)


# ---------- step 3: lift, forecast, cover ----------

LAST_YEAR = date(2025, 10, 31)


def lift_for(before_units, after_units):
    st = stores([("S1", "A", "North", OLD)])
    rows = []
    if before_units:
        rows.append((LAST_YEAR - timedelta(days=10), "S1", "A-M", before_units))
    if after_units:
        rows.append((LAST_YEAR + timedelta(days=5), "S1", "A-M", after_units))
    bills, lines = sales(rows)
    return zone_lift(st, bills, lines, TODAY)["North"]


def test_lift_is_after_rate_over_before_rate():
    # before: 84 units / 84 days = 1/day; after: 60 / 30 = 2/day.
    assert lift_for(84, 60) == pytest.approx(2.0)


def test_lift_capped_both_ends():
    assert lift_for(84, 300) == pytest.approx(3.0)
    assert lift_for(84, 10) == pytest.approx(1.0)


def test_lift_without_before_sales_is_one():
    assert lift_for(0, 50) == pytest.approx(1.0)


def test_lift_ignores_sales_outside_windows():
    st = stores([("S1", "A", "North", OLD)])
    bills, lines = sales([
        (LAST_YEAR - timedelta(days=84), "S1", "A-M", 500),  # before the before-window
        (LAST_YEAR - timedelta(days=1), "S1", "A-M", 84),
        (LAST_YEAR + timedelta(days=31), "S1", "A-M", 500),  # after the after-window
        (LAST_YEAR + timedelta(days=30), "S1", "A-M", 45),
    ])
    assert zone_lift(st, bills, lines, TODAY)["North"] == pytest.approx(1.5)


def cover_fixture():
    t = pd.DataFrame(
        [("S1", "A-M", "A", "North", 0.5), ("S1", "A-L", "A", "North", 0.0), ("S1", "B-M", "B", "North", 0.0)],
        columns=["store_id", "sku_id", "style_id", "zone", "velocity"],
    )
    snap = pd.DataFrame(
        [("S1", "A-M", 8, 2), ("S1", "A-L", 5, 0), ("WH-KOL", "A-M", 100, 0)],
        columns=["location_id", "sku_id", "on_hand", "in_transit"],
    )
    return add_forecast_and_cover(t, {"North": 2.0}, snap)


def test_forecast_and_cover():
    t = cover_fixture()
    a = row(t, "S1", "A-M")
    assert a["forecast_daily"] == pytest.approx(1.0)
    assert a["cover_days"] == pytest.approx(10.0)  # (8 + 2) / 1.0
    assert row(t, "S1", "A-L")["cover_days"] is None
    b = row(t, "S1", "B-M")
    assert (b["on_hand"], b["in_transit"], b["cover_days"]) == (0, 0, None)
    assert len(t) == 3  # warehouse rows never become store rows


def test_style_roll_up():
    styles = style_cover(cover_fixture()).set_index("style_id")
    assert styles.loc["A", "stock"] == 15
    assert styles.loc["A", "forecast_daily"] == pytest.approx(1.0)
    assert styles.loc["A", "cover_days"] == pytest.approx(15.0)
    assert styles.loc["B", "cover_days"] is None


# ---------- real data ----------

@pytest.fixture(scope="module")
def demand():
    ds = load_data()
    return build_demand(ds, find_data_issues(ds))


# Hand-computed with the csv module from data/raw: sum of bill_lines.qty for bills
# dated 2026-08-09..2026-10-31 at the store, over the sum of stock_weekly.days_in_stock
# for the 12 weeks ending 2026-08-15..2026-10-31.
HAND_COMPUTED = [
    ("LKO-01", "KUR-01-L", 50, 71),
    ("BLR-01", "IW-01-M", 5, 84),
    ("PAT-01", "SHW-01-M", 4, 48),
]


@pytest.mark.parametrize("store, sku, units, days", HAND_COMPUTED)
def test_real_velocity_matches_hand_computation(demand, store, sku, units, days):
    r = row(demand.skus, store, sku)
    assert (r["units_84"], r["days_in_stock_84"]) == (units, days)
    assert r["velocity_source"] == "own"
    assert r["velocity"] == pytest.approx(units / days)


def test_real_blr05_uses_peer_velocity(demand):
    skus = demand.skus
    blr05 = skus[skus["store_id"] == "BLR-05"]
    assert len(blr05) > 0
    assert not (blr05["velocity_source"] == "own").any()
    # A qualifying peer: another B store, open 60+ days, with 14+ days in stock for the SKU.
    opened = load_data().stores.set_index("store_id")["opened_on"]
    old_enough = skus["store_id"].map(lambda s: (TODAY - opened[s]).days >= 60)
    peers = skus[(skus["tier"] == "B") & (skus["store_id"] != "BLR-05")
                 & (skus["days_in_stock_84"] >= 14) & old_enough]
    has_peer = blr05["sku_id"].isin(set(peers["sku_id"]))
    assert has_peer.any()
    assert blr05.loc[has_peer, "velocity_source"].str.startswith("peer_").all()
    assert (blr05.loc[~has_peer, "velocity_source"] == "own_thin").all()


def test_real_zone_lifts_in_range(demand):
    assert set(demand.zone_lift) == {"North", "East", "South"}
    assert all(1.0 <= v <= 3.0 for v in demand.zone_lift.values())


def test_real_lko01_kur04_high_forecast(demand):
    kur04 = demand.skus[(demand.skus["store_id"] == "LKO-01") & (demand.skus["style_id"] == "KUR-04")]
    assert len(kur04) > 0
    assert kur04["velocity_source"].str.startswith("peer_").all()
    styles = demand.styles[demand.styles["style_id"] == "KUR-04"].set_index("store_id")
    assert styles.loc["LKO-01", "forecast_daily"] > styles["forecast_daily"].median()


def test_real_excluded_pairs_have_no_demand_row(demand):
    keys = set(zip(demand.skus["store_id"], demand.skus["sku_id"]))
    assert ("KNP-03", "SHW-02-L") not in keys
    assert ("MYS-02", "KUR-02-M") not in keys
    assert len(demand.skus) == 20 * 382 - 2
