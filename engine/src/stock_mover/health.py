"""Summarize cleaned snapshot stock and projected capacity exceptions."""

from collections import defaultdict
from statistics import median

import pandas as pd

from stock_mover.allocate import Key, display_category, min_display_map
from stock_mover.contract import MinDisplayGap, Move, StoreHealth
from stock_mover.loader import Dataset


def store_health(table: pd.DataFrame, ds: Dataset, moves: list[Move]) -> list[StoreHealth]:
    totals = table.groupby("store_id")[["on_hand", "in_transit", "forecast_daily", "velocity"]].sum()
    stock_by_category: dict[Key, int] = defaultdict(int)
    for row in table.itertuples(index=False):
        stock_by_category[row.store_id, display_category(row.category)] += int(row.on_hand + row.in_transit)

    projected_change: dict[str, int] = defaultdict(int)
    for move in moves:
        projected_change[move.from_location] -= move.units
        projected_change[move.to_location] += move.units

    minimums = min_display_map(ds.min_display)
    stores = list(ds.stores.sort_values("store_id").itertuples(index=False))
    totals = totals.reindex([store.store_id for store in stores], fill_value=0)
    fills = {}
    tier_fills: dict[str, list[float]] = defaultdict(list)
    tier_rates: dict[str, list[float]] = defaultdict(list)
    for store in stores:
        row = totals.loc[store.store_id]
        fill = 100 * (row.on_hand + row.in_transit) / store.stock_capacity_units
        fills[store.store_id] = fill
        tier_fills[store.tier].append(fill)
        tier_rates[store.tier].append(row.velocity)
    median_fill = {tier: median(values) for tier, values in tier_fills.items()}
    median_rate = {tier: median(values) for tier, values in tier_rates.items()}

    health = []
    for store in stores:
        location, tier = store.store_id, store.tier
        row = totals.loc[location]
        on_hand, in_transit = int(row.on_hand), int(row.in_transit)
        total = on_hand + in_transit
        gaps = []
        for (display_tier, category), minimum in sorted(minimums.items()):
            units = stock_by_category[location, category]
            if display_tier == tier and units < minimum:
                gaps.append(MinDisplayGap(category=category, min_display_units=minimum, units=units, gap=minimum - units))

        flags = []
        if gaps or (row.velocity > median_rate[tier] and fills[location] < median_fill[tier]):
            flags.append("under_stocked")
        if total + projected_change[location] > store.stock_capacity_units:
            flags.append("over_capacity")
        health.append(StoreHealth(
            store_id=location, city=store.city, zone=store.zone, tier=tier,
            capacity_units=store.stock_capacity_units, units_on_hand=on_hand, units_in_transit=in_transit,
            fill_pct=round(fills[location], 1),
            days_of_cover=round(total / row.forecast_daily, 1) if row.forecast_daily > 0 else None,
            min_display_gaps=gaps, flags=flags,
        ))
    return health
