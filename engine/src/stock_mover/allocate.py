"""Warehouse to store: targets, needs net of in-transit, fair-share allocation and moves."""

import heapq
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd

from stock_mover.checks import exclude_pairs
from stock_mover.constants import (
    DISPLAY_CATEGORY,
    SENIOR_APPROVAL_MRP,
    TARGET_EXTRA_DAYS,
    VELOCITY_WINDOW_DAYS,
    WAREHOUSE_ID,
)
from stock_mover.contract import DataIssue, Move, MoveNumbers

Key = tuple[str, str]  # (store_id, sku_id)


def display_category(category: str) -> str:
    return DISPLAY_CATEGORY.get(category, category)


# ---------- step 1: targets, needs, supply, headroom ----------

def warehouse_lead_days(stores: pd.DataFrame, lead_times: pd.DataFrame) -> dict[str, int]:
    """Store id -> days from the warehouse, from the route for the store's zone."""
    pattern = re.compile(rf"Warehouse {re.escape(WAREHOUSE_ID)} to store, (\w+) zone\b")
    by_zone = {}
    for route, days in zip(lead_times["route"], lead_times["days"]):
        match = pattern.match(route)
        if match:
            by_zone[match.group(1)] = int(days)
    lead = {}
    for store_id, zone in zip(stores["store_id"], stores["zone"]):
        if zone not in by_zone:
            raise ValueError(f"No warehouse lead time for zone {zone} (store {store_id})")
        lead[store_id] = by_zone[zone]
    return lead


def warehouse_supply(snapshot: pd.DataFrame, issues: list[DataIssue]) -> dict[str, int]:
    """SKU -> warehouse on hand; inbound deliveries are later supply and not spent today."""
    wh = exclude_pairs(snapshot[snapshot["location_id"] == WAREHOUSE_ID], issues, "location_id")
    totals = wh.groupby("sku_id")["on_hand"].sum()
    return {sku: int(units) for sku, units in totals.items() if units > 0}


def store_headroom(skus: pd.DataFrame, stores: pd.DataFrame) -> dict[str, int]:
    """Store id -> capacity left after on hand and in transit (demand table, so excluded rows don't count)."""
    stock = (skus["on_hand"] + skus["in_transit"]).groupby(skus["store_id"]).sum()
    return {
        store_id: max(0, int(capacity) - int(stock.get(store_id, 0)))
        for store_id, capacity in zip(stores["store_id"], stores["stock_capacity_units"])
    }


def _round_half_up(x: float) -> int:
    return math.floor(x + 0.5)


def add_targets(skus: pd.DataFrame, lead_days: dict[str, int]) -> pd.DataFrame:
    """Target = forecast x (lead days + 30); need = target - (on hand + in transit), never negative."""
    table = skus.copy()
    table["lead_days"] = table["store_id"].map(lead_days).astype("int64")
    table["target"] = [
        _round_half_up(f * (lead + TARGET_EXTRA_DAYS)) for f, lead in zip(table["forecast_daily"], table["lead_days"])
    ]
    table["target"] = table["target"].astype("int64")
    table["need"] = (table["target"] - table["on_hand"] - table["in_transit"]).clip(lower=0).astype("int64")
    return table


# ---------- step 2: allocation ----------

@dataclass
class Allocation:
    units: dict[Key, int] = field(default_factory=dict)
    min_display_units: dict[Key, int] = field(default_factory=dict)
    headroom_left: dict[str, int] = field(default_factory=dict)
    # Projected cover of the store-SKU just before its last fair-share unit.
    last_unit_cover: dict[Key, float] = field(default_factory=dict)


def _min_display_map(min_display: pd.DataFrame) -> dict[tuple[str, str], int]:
    return {(t, c): int(u) for t, c, u in zip(min_display["tier"], min_display["category"],
                                              min_display["min_display_units"])}


def allocate(table: pd.DataFrame, supply: dict[str, int], headroom: dict[str, int],
             min_display: pd.DataFrame) -> Allocation:
    """Phase A fills min display gaps; phase B gives one unit at a time to the lowest projected cover."""
    supply = dict(supply)
    headroom = dict(headroom)
    units: dict[Key, int] = defaultdict(int)
    md_units: dict[Key, int] = defaultdict(int)
    rows = table.sort_values(["store_id", "sku_id"])
    stock = {(s, k): int(o + t) for s, k, o, t in zip(rows["store_id"], rows["sku_id"], rows["on_hand"],
                                                      rows["in_transit"])}
    forecast = dict(zip(zip(rows["store_id"], rows["sku_id"]), rows["forecast_daily"].astype(float)))

    def give(key: Key) -> None:
        units[key] += 1
        supply[key[1]] -= 1
        headroom[key[0]] -= 1

    # Phase A: min display floor per store and display category.
    minimums = _min_display_map(min_display)
    groups: dict[tuple[str, str, str], list[Key]] = defaultdict(list)
    for s, k, cat, tier in zip(rows["store_id"], rows["sku_id"], rows["category"], rows["tier"]):
        groups[(s, display_category(cat), tier)].append((s, k))
    for (store, dcat, tier), keys in sorted(groups.items()):
        minimum = minimums.get((tier, dcat))
        if minimum is None:
            continue
        gap = minimum - sum(stock[k] for k in keys)
        while gap > 0 and headroom.get(store, 0) > 0:
            candidates = [k for k in keys if supply.get(k[1], 0) > 0]
            if not candidates:
                break
            key = min(candidates, key=lambda k: (stock[k] + units[k], -forecast[k], k[1]))
            give(key)
            md_units[key] += 1
            gap -= 1

    # Phase B: fair share by lowest projected cover.
    need = dict(zip(zip(rows["store_id"], rows["sku_id"]), rows["need"].astype(int)))
    last_cover: dict[Key, float] = {}

    def entry(key: Key) -> tuple:
        return ((stock[key] + units[key]) / forecast[key], -forecast[key], key[0], key[1])

    heap = [entry(k) for k, n in need.items() if n > units[k] and forecast[k] > 0]
    heapq.heapify(heap)
    while heap:
        cover, _, store, sku = heapq.heappop(heap)
        key = (store, sku)
        if supply.get(sku, 0) <= 0 or headroom.get(store, 0) <= 0:
            continue
        give(key)
        last_cover[key] = cover
        if need[key] > units[key]:
            heapq.heappush(heap, entry(key))

    return Allocation(
        units={k: u for k, u in sorted(units.items()) if u > 0},
        min_display_units={k: u for k, u in sorted(md_units.items()) if u > 0},
        headroom_left=headroom,
        last_unit_cover=last_cover,
    )


# ---------- step 3: moves ----------

def _fmt_date(d: date) -> str:
    return f"{d.day} {d:%b}"


def _cover(stock: int, forecast: float) -> float | None:
    return round(stock / forecast, 1) if forecast > 0 else None


def _cover_text(cover: float | None) -> str:
    return "no recent sales" if cover is None else f"{cover:.1f} days of cover"


def _reason(row, units: int, has_min_display: bool, category_stock: int, minimum: int | None,
            cover_before: float | None, arrives: date) -> str:
    store, sku = row.store_id, row.sku_id
    if has_min_display:
        opening = (f"{store} has {category_stock} {display_category(row.category)} on display vs a minimum of "
                   f"{minimum} for a {row.tier} store.")
    elif row.velocity_source in ("peer_zone", "peer_network"):
        opening = (f"Similar {row.tier} stores sell {row.velocity:.1f} a day of {sku}; "
                   f"{store} has {_cover_text(cover_before)}.")
    elif row.days_in_stock_84 < VELOCITY_WINDOW_DAYS:
        opening = (f"{store} had {sku} in stock only {row.days_in_stock_84} of {VELOCITY_WINDOW_DAYS} days "
                   f"and still sold {row.units_84}; {_cover_text(cover_before)}.")
    else:
        opening = (f"{store} sells {row.forecast_daily:.1f} a day of {sku} (season lift {row.lift:.2f}); "
                   f"{_cover_text(cover_before)} vs {row.lead_days + TARGET_EXTRA_DAYS} needed.")
    return f"{opening} Send {units} from {WAREHOUSE_ID}, arrives {_fmt_date(arrives)}."


def warehouse_moves(table: pd.DataFrame, alloc: Allocation, items: pd.DataFrame,
                    min_display: pd.DataFrame, today: date) -> list[Move]:
    """One warehouse_to_store move per allocated store-SKU, highest priority first."""
    item = items.set_index("sku_id")
    rows = {(r.store_id, r.sku_id): r for r in table.itertuples(index=False)}
    minimums = _min_display_map(min_display)
    category_stock: dict[tuple[str, str], int] = defaultdict(int)
    for r in rows.values():
        category_stock[(r.store_id, display_category(r.category))] += int(r.on_hand + r.in_transit)

    moves = []
    for key, units in alloc.units.items():
        row = rows[key]
        stock = int(row.on_hand + row.in_transit)
        forecast = float(row.forecast_daily)
        mrp = int(item.at[row.sku_id, "mrp"])
        value = float(units * mrp)
        arrives = today + timedelta(days=int(row.lead_days))
        cover_before = _cover(stock, forecast)
        dcat = display_category(row.category)
        has_min_display = alloc.min_display_units.get(key, 0) > 0
        moves.append(Move(
            id=f"w2s-{row.store_id}-{row.sku_id}",
            type="warehouse_to_store",
            sku_id=row.sku_id,
            style_id=row.style_id,
            style_name=str(item.at[row.sku_id, "style_name"]),
            category=row.category,
            size=row.size,
            from_location=WAREHOUSE_ID,
            to_location=row.store_id,
            units=units,
            value_mrp=value,
            lead_days=int(row.lead_days),
            arrives_on=arrives,
            priority=round(value, 2),
            reason=_reason(row, units, has_min_display, category_stock[(row.store_id, dcat)],
                           minimums.get((row.tier, dcat)), cover_before, arrives),
            needs_senior_approval=value > SENIOR_APPROVAL_MRP,
            numbers=MoveNumbers(
                velocity=round(float(row.velocity), 2),
                days_in_stock_84=int(row.days_in_stock_84),
                cover_before=cover_before,
                cover_after=_cover(stock + units, forecast),
                lift=round(float(row.lift), 2),
            ),
        ))
    return sorted(moves, key=lambda m: (-m.priority, m.id))
