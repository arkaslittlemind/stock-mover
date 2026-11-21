"""Plan store transfers and warehouse returns after warehouse replenishment."""

from collections import defaultdict
from datetime import date, timedelta
from math import ceil

import pandas as pd

from stock_mover.allocate import (
    Allocation, Key, display_category, min_display_map, move_numbers, warehouse_lead_days,
)
from stock_mover.constants import (
    AGEING_MIN_AGE_DAYS,
    AGEING_MIN_COVER_DAYS,
    DONOR_MIN_COVER_DAYS,
    PEER_MIN_DAYS_IN_STOCK,
    SENIOR_APPROVAL_MRP,
    WAREHOUSE_ID,
)
from stock_mover.contract import DataIssue, Move
from stock_mover.loader import Dataset


def store_transfer_lead_days(source, destination, routes: dict[str, int]) -> int:
    if source.city == destination.city and source.zone == destination.zone:
        return routes["Store to store, same city"]
    if source.zone == destination.zone:
        return routes["Store to store, same zone, different city"]
    return routes["Store to store, different zone"]


def ageing_cover_reason(row, stock: int) -> str | None:
    if row.forecast_daily > 0:
        cover = stock / row.forecast_daily
        return f"{cover:.1f} days of cover" if cover > AGEING_MIN_COVER_DAYS else None
    if stock > 0 and row.velocity_source == "own" and row.days_in_stock_84 >= PEER_MIN_DAYS_IN_STOCK:
        return f"no sales in {row.days_in_stock_84} days in stock"
    return None


class StorePlan:
    """Balances that all store planning passes update after allocating a move."""

    def __init__(
        self, table: pd.DataFrame, warehouse: Allocation, ds: Dataset, today: date,
        issues: list[DataIssue],
    ) -> None:
        self.rows = {(r.store_id, r.sku_id): r for r in table.itertuples(index=False)}
        self.stores = {r.store_id: r for r in ds.stores.itertuples(index=False)}
        self.items = {r.sku_id: r for r in ds.items.itertuples(index=False)}
        self.routes = dict(zip(ds.lead_times["route"], ds.lead_times["days"]))
        self.return_days = warehouse_lead_days(ds.stores, ds.lead_times)
        self.protected = set(zip(ds.flagship_protected["store_id"], ds.flagship_protected["style_id"]))
        self.excluded = {(issue.location_id, issue.sku_id) for issue in issues if issue.excluded}
        self.minimums = min_display_map(ds.min_display)
        self.today = today
        self.moves: list[Move] = []
        self.planned_routes: set[tuple[str, str, str]] = set()
        self.donor_styles: set[Key] = set()
        self.available = {key: int(row.on_hand) for key, row in self.rows.items()}
        self.projected: dict[Key, int] = {}
        self.store_stock: dict[str, int] = defaultdict(int)
        # Approval is per move. Pending receipts cannot fund donors, and
        # pending departures cannot make room for receipts.
        self.receiving_room = warehouse.headroom_left.copy()
        self.donor_category_stock: dict[Key, int] = defaultdict(int)
        self.donor_style_stock: dict[Key, int] = defaultdict(int)
        self.style_forecast: dict[Key, float] = defaultdict(float)
        self.style_velocity: dict[Key, float] = defaultdict(float)
        for (store, sku), row in self.rows.items():
            stock = int(row.on_hand + row.in_transit)
            self.adjust_projected(store, sku, stock + warehouse.units.get((store, sku), 0))
            self.donor_category_stock[store, display_category(row.category)] += stock
            self.donor_style_stock[store, row.style_id] += stock
            self.style_forecast[store, row.style_id] += float(row.forecast_daily)
            self.style_velocity[store, row.style_id] += float(row.velocity)

    def adjust_projected(self, store: str, sku: str, change: int) -> None:
        self.projected[store, sku] = self.projected.get((store, sku), 0) + change
        self.store_stock[store] += change

    def transferable(self, source: str, sku: str, to_store: bool) -> int:
        row = self.rows[source, sku]
        if row.tier == "S++" and (source, row.style_id) in self.protected:
            return 0
        category = display_category(row.category)
        minimum = self.minimums.get((row.tier, category), 0)
        units = min(self.available[source, sku], self.donor_category_stock[source, category] - minimum)
        if to_store or (source, row.style_id) in self.donor_styles:
            floor = ceil(DONOR_MIN_COVER_DAYS * self.style_forecast[source, row.style_id])
            units = min(units, self.donor_style_stock[source, row.style_id] - floor)
        return max(0, units)

    def record(
        self, purpose: str, source: str, destination: str, sku: str, units: int, reason: str,
    ) -> None:
        pullback = destination == WAREHOUSE_ID
        store = source if pullback else destination
        row = self.rows[store, sku]
        lead_days = (
            self.return_days[source] if pullback
            else store_transfer_lead_days(self.stores[source], self.stores[destination], self.routes)
        )
        arrives = self.today + timedelta(days=int(lead_days))
        value = float(units * self.items[sku].mrp)
        before = self.projected[store, sku]
        self.moves.append(Move(
            id=f"{purpose}-{source}-{destination}-{sku}",
            type="pull_back" if pullback else "store_to_store",
            sku_id=sku,
            style_id=row.style_id,
            style_name=self.items[sku].style_name,
            category=row.category,
            size=row.size,
            from_location=source,
            to_location=destination,
            units=units,
            value_mrp=value,
            lead_days=lead_days,
            arrives_on=arrives,
            priority=value,
            reason=f"{reason} Send {units} from {source} to {destination}, arriving {arrives.day} {arrives:%b}.",
            needs_senior_approval=value > SENIOR_APPROVAL_MRP,
            numbers=move_numbers(row, before, before - units if pullback else before + units),
        ))
        self.planned_routes.add((source, destination, sku))
        self.available[source, sku] -= units
        self.donor_category_stock[source, display_category(row.category)] -= units
        self.donor_style_stock[source, row.style_id] -= units
        self.adjust_projected(source, sku, -units)
        if not pullback:
            self.donor_styles.add((source, row.style_id))
            self.receiving_room[destination] -= units
            self.adjust_projected(destination, sku, units)

    def rebalance(self) -> None:
        donors_by_sku: dict[str, list[str]] = defaultdict(list)
        for (store, sku), row in self.rows.items():
            if self.available[store, sku] > 0 and self.available[store, sku] + row.in_transit > row.target:
                donors_by_sku[sku].append(store)

        needs = [
            key for key, row in self.rows.items()
            if self.projected[key] < row.target and row.forecast_daily > 0
        ]
        needs.sort(key=lambda key: (self.projected[key] / self.rows[key].forecast_daily, key))
        for destination, sku in needs:
            recipient = self.rows[destination, sku]
            candidates = sorted(
                (store_transfer_lead_days(self.stores[source], self.stores[destination], self.routes), source)
                for source in donors_by_sku[sku]
                if source != destination
            )
            for _, source in candidates:
                need = recipient.target - self.projected[destination, sku]
                remaining = min(need, self.receiving_room[destination])
                if remaining <= 0:
                    break
                donor = self.rows[source, sku]
                units = min(
                    remaining,
                    self.transferable(source, sku, to_store=True),
                    self.available[source, sku] + donor.in_transit - donor.target,
                )
                if units > 0:
                    self.record(
                        "s2s", source, destination, sku, units,
                        f"{destination} still needs {need} of {sku} after warehouse allocation.",
                    )

    def move_ageing(self, snapshot: pd.DataFrame) -> None:
        for stock in snapshot.sort_values(["location_id", "sku_id"]).itertuples(index=False):
            source, sku = stock.location_id, stock.sku_id
            key = (source, sku)
            if key not in self.rows or not stock.oldest_stock_received_on or not self.available[key]:
                continue
            age = (self.today - stock.oldest_stock_received_on).days
            if age <= AGEING_MIN_AGE_DAYS:
                continue
            row = self.rows[key]
            # New recommendations do not make a previously healthy SKU old.
            cover_text = ageing_cover_reason(row, self.available[key] + row.in_transit)
            if cover_text is None:
                continue

            reason = f"{source}'s oldest {sku} stock arrived {age} days ago, with {cover_text}."
            destinations = sorted(
                (store for store in self.stores if store != source and (store, sku) in self.rows
                 and self.style_velocity[store, row.style_id] > 0 and self.receiving_room[store] > 0
                 and (store, source, sku) not in self.planned_routes),
                key=lambda store: (
                    -self.style_velocity[store, row.style_id],
                    store_transfer_lead_days(self.stores[source], self.stores[store], self.routes),
                    store,
                ),
            )
            for destination in destinations:
                units = min(self.transferable(source, sku, to_store=True), self.receiving_room[destination])
                if units <= 0:
                    break
                rate = self.style_velocity[destination, row.style_id]
                self.record(
                    "age", source, destination, sku, units,
                    f"{reason} {destination} sells {rate:.2f} units of the style per day.",
                )
            units = self.transferable(source, sku, to_store=False)
            if units > 0 and (WAREHOUSE_ID, sku) not in self.excluded:
                self.record("age", source, WAREHOUSE_ID, sku, units, reason)

    def relieve_capacity(self) -> None:
        for store in sorted(self.stores):
            capacity = self.stores[store].stock_capacity_units
            if self.store_stock[store] <= capacity:
                continue
            candidates = sorted(
                (row for (source, sku), row in self.rows.items()
                 if source == store and (WAREHOUSE_ID, sku) not in self.excluded),
                key=lambda row: (row.velocity, row.sku_id),
            )
            for row in candidates:
                excess = self.store_stock[store] - capacity
                if excess <= 0:
                    break
                units = min(excess, self.transferable(store, row.sku_id, to_store=False))
                if units > 0:
                    self.record(
                        "capacity", store, WAREHOUSE_ID, row.sku_id, units,
                        f"{store} is {excess} units over capacity and sells {row.sku_id} at {row.velocity:.2f} per day.",
                    )


def plan_store_moves(
    table: pd.DataFrame, warehouse: Allocation, ds: Dataset, today: date, issues: list[DataIssue],
) -> list[Move]:
    """Allocate store moves against the warehouse plan and the cleaned demand rows."""
    plan = StorePlan(table, warehouse, ds, today, issues)
    plan.rebalance()
    plan.move_ageing(ds.stock_snapshot)
    plan.relieve_capacity()
    return plan.moves
