from dataclasses import replace
from datetime import date

import pandas as pd
import pytest

from stock_mover.checks import (
    exclude_pairs,
    find_data_issues,
    negative_stock,
    snapshot_vs_weekly,
    unknown_ids,
)
from stock_mover.loader import load_data

WEEK = date(2026, 10, 31)


def snapshot(rows):
    return pd.DataFrame(rows, columns=["location_id", "sku_id", "on_hand", "in_transit"])


def weekly(rows):
    df = pd.DataFrame(rows, columns=["store_id", "sku_id", "closing_on_hand"])
    df["week_ending"] = WEEK
    return df


@pytest.fixture(scope="module")
def ds():
    return load_data()


def test_negative_on_hand_flagged():
    findings = negative_stock(snapshot([("S1", "A", -2, 0), ("S1", "B", 3, 0)]))
    assert [(f[0], f[1], f[2]) for f in findings] == [("S1", "A", "negative_stock")]
    assert "-2" in findings[0][3]


def test_negative_in_transit_flagged():
    findings = negative_stock(snapshot([("S1", "A", 1, -1)]))
    assert findings[0][2] == "negative_stock"


def test_missing_snapshot_row_vs_zero_close_not_flagged():
    assert snapshot_vs_weekly(snapshot([]), weekly([("S1", "A", 0)])) == []


def test_missing_snapshot_row_vs_positive_close_flagged():
    findings = snapshot_vs_weekly(snapshot([]), weekly([("S1", "A", 5)]))
    assert [(f[0], f[1]) for f in findings] == [("S1", "A")]
    assert "0 on hand" in findings[0][3] and "shows 5" in findings[0][3]


def test_matching_stock_not_flagged():
    assert snapshot_vs_weekly(snapshot([("S1", "A", 4, 0)]), weekly([("S1", "A", 4)])) == []


def test_warehouse_never_compared_with_weekly():
    assert snapshot_vs_weekly(snapshot([("WH-KOL", "A", 50, 0)]), weekly([])) == []


def test_only_latest_week_compared():
    old = weekly([("S1", "A", 9)])
    old["week_ending"] = date(2026, 10, 24)
    both = pd.concat([old, weekly([("S1", "A", 4)])])
    assert snapshot_vs_weekly(snapshot([("S1", "A", 4, 0)]), both) == []


def test_unknown_ids_flagged(ds):
    small = replace(
        ds,
        stock_snapshot=snapshot([("LKO-01", "NOPE-1", 1, 0), ("XXX-9", "KUR-01-M", 1, 0), ("WH-KOL", "KUR-01-M", 1, 0)]),
        stock_weekly=weekly([]),
        warehouse_inbound=ds.warehouse_inbound.head(0),
        bill_lines=ds.bill_lines.head(0),
    )
    found = {(f[0], f[1], f[2]) for f in unknown_ids(small)}
    assert found == {("LKO-01", "NOPE-1", "unknown_sku"), ("XXX-9", "KUR-01-M", "unknown_location")}


def test_two_checks_on_one_pair_merge_into_one_issue(ds):
    small = replace(
        ds,
        stock_snapshot=snapshot([("LKO-01", "KUR-01-M", -4, 0)]),
        stock_weekly=weekly([("LKO-01", "KUR-01-M", 3)]),
        warehouse_inbound=ds.warehouse_inbound.head(0),
        bill_lines=ds.bill_lines.head(0),
    )
    issues = find_data_issues(small)
    assert len(issues) == 1
    assert issues[0].checks == ["negative_stock", "snapshot_vs_weekly"]
    assert issues[0].note.endswith("Excluded from moves.")


def test_real_data_flags_exactly_the_planted_errors(ds):
    issues = find_data_issues(ds)
    assert [(i.location_id, i.sku_id) for i in issues] == [("KNP-03", "SHW-02-L"), ("MYS-02", "KUR-02-M")]
    knp, mys = issues
    assert "300" in knp.note and "shows 0" in knp.note
    assert "-4" in mys.note and "shows 3" in mys.note
    assert knp.excluded and mys.excluded


def test_exclude_pairs_removes_exactly_the_flagged_rows(ds):
    issues = find_data_issues(ds)
    kept = exclude_pairs(ds.stock_snapshot, issues, "location_id")
    assert len(kept) == len(ds.stock_snapshot) - 2
    pairs = set(zip(kept["location_id"], kept["sku_id"]))
    assert ("KNP-03", "SHW-02-L") not in pairs and ("MYS-02", "KUR-02-M") not in pairs
