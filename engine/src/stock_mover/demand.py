"""Demand: per-day-in-stock velocity, peer velocity, season lift, forecast and cover."""

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from stock_mover.checks import exclude_pairs
from stock_mover.constants import (
    LIFT_AFTER_DAYS,
    LIFT_MAX,
    LIFT_MIN,
    NEW_STORE_DAYS,
    NEW_STYLE_DAYS,
    PEER_MIN_DAYS_IN_STOCK,
    TODAY,
    VELOCITY_WINDOW_DAYS,
)
from stock_mover.contract import DataIssue
from stock_mover.loader import Dataset


@dataclass(frozen=True)
class Demand:
    skus: pd.DataFrame
    styles: pd.DataFrame
    zone_lift: dict[str, float]


def units_sold(bills: pd.DataFrame, bill_lines: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """Units per store-SKU for bills dated start to end inclusive."""
    in_window = bills[(bills["bill_date"] >= start) & (bills["bill_date"] <= end)]
    lines = bill_lines.merge(in_window[["bill_id", "store_id"]], on="bill_id")
    return lines.groupby(["store_id", "sku_id"], as_index=False)["qty"].sum().rename(columns={"qty": "units"})


def base_table(
    stores: pd.DataFrame,
    items: pd.DataFrame,
    bills: pd.DataFrame,
    bill_lines: pd.DataFrame,
    weekly: pd.DataFrame,
    today: date = TODAY,
) -> pd.DataFrame:
    """Every store x every SKU with 84-day units, days in stock and own velocity (missing = 0)."""
    start = today - timedelta(days=VELOCITY_WINDOW_DAYS - 1)
    store_cols = stores[["store_id", "tier", "zone", "opened_on"]]
    item_cols = items[["sku_id", "style_id", "category", "size", "launch_date"]]
    table = store_cols.merge(item_cols, how="cross")

    sales = units_sold(bills, bill_lines, start, today).rename(columns={"units": "units_84"})
    in_window = weekly[(weekly["week_ending"] > today - timedelta(days=VELOCITY_WINDOW_DAYS))
                       & (weekly["week_ending"] <= today)]
    days = (in_window.groupby(["store_id", "sku_id"], as_index=False)["days_in_stock"].sum()
            .rename(columns={"days_in_stock": "days_in_stock_84"}))

    table = table.merge(sales, on=["store_id", "sku_id"], how="left")
    table = table.merge(days, on=["store_id", "sku_id"], how="left")
    table[["units_84", "days_in_stock_84"]] = table[["units_84", "days_in_stock_84"]].fillna(0).astype("int64")
    table["days_in_stock_84"] = table["days_in_stock_84"].clip(0, VELOCITY_WINDOW_DAYS)
    days_f = table["days_in_stock_84"].astype(float)
    table["own_velocity"] = (table["units_84"] / days_f.where(days_f > 0)).fillna(0.0)
    return table


def _days_since(d: date | None, today: date) -> int | None:
    return None if d is None or pd.isna(d) else (today - d).days


def _store_rates(table: pd.DataFrame, today: date) -> dict[str, float]:
    """Each store's total units per day open in the window."""
    rates = {}
    for store_id, rows in table.groupby("store_id"):
        open_days = min(VELOCITY_WINDOW_DAYS, max(1, _days_since(rows["opened_on"].iloc[0], today) + 1))
        rates[store_id] = rows["units_84"].sum() / open_days
    return rates


def apply_peer_velocity(table: pd.DataFrame, today: date = TODAY) -> pd.DataFrame:
    """Set velocity and velocity_source; thin history borrows same-tier peers' rate, scaled."""
    table = table.copy()
    store_age = table["opened_on"].map(lambda d: _days_since(d, today))
    style_age = table["launch_date"].map(lambda d: _days_since(d, today))
    new_store = store_age < NEW_STORE_DAYS
    new_style = style_age.map(lambda a: a is not None and a < NEW_STYLE_DAYS)
    thin = table["days_in_stock_84"] < PEER_MIN_DAYS_IN_STOCK
    needs_peers = thin | new_store | new_style
    qualifies = ~thin & ~new_store

    rates = _store_rates(table, today)
    peers: dict[tuple[str, str], list[tuple[str, str, int, int]]] = {}
    for row in table[qualifies].itertuples():
        peers.setdefault((row.sku_id, row.tier), []).append(
            (row.store_id, row.zone, row.units_84, row.days_in_stock_84)
        )

    velocity = table["own_velocity"].astype(float).tolist()
    source = ["own"] * len(table)
    for i, row in enumerate(table.itertuples()):
        if not needs_peers.iloc[i]:
            continue
        others = [p for p in peers.get((row.sku_id, row.tier), []) if p[0] != row.store_id]
        zone_peers = [p for p in others if p[1] == row.zone]
        chosen, label = (zone_peers, "peer_zone") if zone_peers else (others, "peer_network")
        if not chosen:
            source[i] = "own_thin"
            continue
        peer_rate = sum(p[2] for p in chosen) / sum(p[3] for p in chosen)
        mean_peer_store_rate = sum(rates[p[0]] for p in chosen) / len(chosen)
        own_rate = rates[row.store_id]
        scale = own_rate / mean_peer_store_rate if own_rate > 0 and mean_peer_store_rate > 0 else 1.0
        velocity[i] = peer_rate * scale
        source[i] = label
    table["velocity"] = velocity
    table["velocity_source"] = source
    return table


def zone_lift(stores: pd.DataFrame, bills: pd.DataFrame, bill_lines: pd.DataFrame,
              today: date = TODAY) -> dict[str, float]:
    """Last year's daily sales in the 30 days after today's date over the 84 days before it, per zone."""
    matching = today.replace(year=today.year - 1)
    before = units_sold(bills, bill_lines, matching - timedelta(days=VELOCITY_WINDOW_DAYS - 1), matching)
    after = units_sold(bills, bill_lines, matching + timedelta(days=1), matching + timedelta(days=LIFT_AFTER_DAYS))
    zone_of = stores.set_index("store_id")["zone"]
    lifts = {}
    for zone in sorted(stores["zone"].unique()):
        before_units = before.loc[before["store_id"].map(zone_of) == zone, "units"].sum()
        after_units = after.loc[after["store_id"].map(zone_of) == zone, "units"].sum()
        if before_units <= 0:
            lifts[zone] = LIFT_MIN
            continue
        lift = (after_units / LIFT_AFTER_DAYS) / (before_units / VELOCITY_WINDOW_DAYS)
        lifts[zone] = float(min(LIFT_MAX, max(LIFT_MIN, lift)))
    return lifts


def _cover(stock: pd.Series, forecast: pd.Series) -> pd.Series:
    cover = stock / forecast.where(forecast > 0)
    return cover.astype(object).where(cover.notna(), None)


def add_forecast_and_cover(table: pd.DataFrame, lifts: dict[str, float], snapshot: pd.DataFrame) -> pd.DataFrame:
    """Forecast = velocity x zone lift; cover = (on hand + in transit) / forecast, None at zero forecast."""
    table = table.copy()
    table["lift"] = table["zone"].map(lifts).fillna(LIFT_MIN).astype(float)
    table["forecast_daily"] = table["velocity"] * table["lift"]
    stock = snapshot[["location_id", "sku_id", "on_hand", "in_transit"]].rename(columns={"location_id": "store_id"})
    table = table.merge(stock, on=["store_id", "sku_id"], how="left")
    table[["on_hand", "in_transit"]] = table[["on_hand", "in_transit"]].fillna(0).astype("int64")
    table["cover_days"] = _cover(table["on_hand"] + table["in_transit"], table["forecast_daily"])
    return table


def style_cover(skus: pd.DataFrame) -> pd.DataFrame:
    """Roll store-SKU stock and forecast up to store-style cover."""
    rolled = skus.assign(stock=skus["on_hand"] + skus["in_transit"])
    styles = rolled.groupby(["store_id", "style_id"], as_index=False)[["stock", "forecast_daily"]].sum()
    styles["stock"] = styles["stock"].astype("int64")
    styles["cover_days"] = _cover(styles["stock"], styles["forecast_daily"])
    return styles


SKU_COLUMNS = [
    "store_id", "sku_id", "style_id", "category", "size", "tier", "zone", "units_84",
    "days_in_stock_84", "own_velocity", "velocity", "velocity_source", "lift",
    "forecast_daily", "on_hand", "in_transit", "cover_days",
]


def build_demand(ds: Dataset, issues: list[DataIssue], today: date = TODAY) -> Demand:
    """Demand per store-SKU and store-style; excluded data-issue pairs get no row and are never peers."""
    table = base_table(ds.stores, ds.items, ds.bills, ds.bill_lines, ds.stock_weekly, today)
    table = exclude_pairs(table, issues, "store_id")
    table = apply_peer_velocity(table, today)
    lifts = zone_lift(ds.stores, ds.bills, ds.bill_lines, today)
    skus = add_forecast_and_cover(table, lifts, ds.stock_snapshot)[SKU_COLUMNS]
    return Demand(skus=skus, styles=style_cover(skus), zone_lift=lifts)
