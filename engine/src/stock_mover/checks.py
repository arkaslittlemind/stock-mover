"""Data checks: each finding becomes a plain-words data issue, excluded from moves."""

import pandas as pd

from stock_mover.constants import WAREHOUSE_ID
from stock_mover.contract import DataCheck, DataIssue
from stock_mover.loader import Dataset

Finding = tuple[str, str, DataCheck, str]


def _fmt_date(d) -> str:
    return f"{d.day} {d:%b}"


def negative_stock(snapshot: pd.DataFrame) -> list[Finding]:
    findings = []
    for row in snapshot[(snapshot["on_hand"] < 0) | (snapshot["in_transit"] < 0)].itertuples():
        field, value = ("on hand", row.on_hand) if row.on_hand < 0 else ("in transit", row.in_transit)
        note = f"Snapshot shows {value} {field}; stock cannot be negative."
        findings.append((row.location_id, row.sku_id, "negative_stock", note))
    return findings


def snapshot_vs_weekly(snapshot: pd.DataFrame, weekly: pd.DataFrame) -> list[Finding]:
    """Compare store on-hand with the latest weekly close; a missing row on either side is 0."""
    last_week = weekly["week_ending"].max()
    close = weekly.loc[weekly["week_ending"] == last_week, ["store_id", "sku_id", "closing_on_hand"]]
    close = close.rename(columns={"store_id": "location_id"})
    stores_only = snapshot.loc[snapshot["location_id"] != WAREHOUSE_ID, ["location_id", "sku_id", "on_hand"]]
    joined = stores_only.merge(close, on=["location_id", "sku_id"], how="outer")
    joined[["on_hand", "closing_on_hand"]] = joined[["on_hand", "closing_on_hand"]].fillna(0).astype("int64")
    findings = []
    for row in joined[joined["on_hand"] != joined["closing_on_hand"]].itertuples():
        note = (
            f"Snapshot shows {row.on_hand} on hand, but the {_fmt_date(last_week)} "
            f"weekly close shows {row.closing_on_hand}."
        )
        findings.append((row.location_id, row.sku_id, "snapshot_vs_weekly", note))
    return findings


def unknown_ids(ds: Dataset) -> list[Finding]:
    skus = set(ds.items["sku_id"])
    stores = set(ds.stores["store_id"])
    bill_store = ds.bills.set_index("bill_id")["store_id"]
    keyed = [
        ("snapshot", ds.stock_snapshot["location_id"], ds.stock_snapshot["sku_id"]),
        ("weekly table", ds.stock_weekly["store_id"], ds.stock_weekly["sku_id"]),
        ("inbound list", pd.Series(WAREHOUSE_ID, index=ds.warehouse_inbound.index), ds.warehouse_inbound["sku_id"]),
        ("sales", ds.bill_lines["bill_id"].map(bill_store).fillna(""), ds.bill_lines["sku_id"]),
    ]
    findings: set[Finding] = set()
    for source, locations, sku_ids in keyed:
        for loc, sku in set(zip(locations, sku_ids)):
            if sku not in skus:
                findings.add((loc, sku, "unknown_sku", f"SKU {sku} in the {source} is not in the item list."))
            if loc not in stores and not (loc == WAREHOUSE_ID and source in {"snapshot", "inbound list"}):
                note = f"Location {loc or '(blank)'} in the {source} is not a known store."
                findings.add((loc, sku, "unknown_location", note))
    return sorted(findings)


def find_data_issues(ds: Dataset) -> list[DataIssue]:
    """All findings, merged to one excluded data issue per location-SKU."""
    findings = (
        negative_stock(ds.stock_snapshot)
        + snapshot_vs_weekly(ds.stock_snapshot, ds.stock_weekly)
        + unknown_ids(ds)
    )
    merged: dict[tuple[str, str], tuple[list[DataCheck], list[str]]] = {}
    for loc, sku, check, note in findings:
        checks, notes = merged.setdefault((loc, sku), ([], []))
        if check not in checks:
            checks.append(check)
            notes.append(note)
    return [
        DataIssue(
            location_id=loc,
            sku_id=sku,
            checks=checks,
            note=" ".join(notes) + " Excluded from moves.",
            excluded=True,
        )
        for (loc, sku), (checks, notes) in sorted(merged.items())
    ]


def exclude_pairs(df: pd.DataFrame, issues: list[DataIssue], location_col: str) -> pd.DataFrame:
    """Drop rows whose (location, SKU) has an excluded data issue."""
    pairs = {(i.location_id, i.sku_id) for i in issues if i.excluded}
    keep = [(loc, sku) not in pairs for loc, sku in zip(df[location_col], df["sku_id"])]
    return df[keep].reset_index(drop=True)
