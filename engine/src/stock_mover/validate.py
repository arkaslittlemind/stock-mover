"""Independently check the complete run against its source data."""

from collections import Counter, defaultdict
from datetime import date, timedelta

import pandas as pd

from stock_mover.allocate import Key, display_category, min_display_map, warehouse_lead_days, warehouse_supply
from stock_mover.constants import AGEING_MIN_AGE_DAYS, DONOR_MIN_COVER_DAYS, SENIOR_APPROVAL_MRP, WAREHOUSE_ID
from stock_mover.contract import DataIssue, Move, RuleResult
from stock_mover.loader import Dataset
from stock_mover.store_moves import ageing_cover_reason, store_transfer_lead_days


class RuleViolation(ValueError):
    """A candidate run failed rule validation."""


def validate_moves(
    moves: list[Move], table: pd.DataFrame, ds: Dataset, issues: list[DataIssue], today: date,
) -> list[RuleResult]:
    """Recheck emitted moves with separate receipt and outbound limits."""
    rows = {(row.store_id, row.sku_id): row for row in table.itertuples(index=False)}
    stores = {row.store_id: row for row in ds.stores.itertuples(index=False)}
    items = {row.sku_id: row for row in ds.items.itertuples(index=False)}
    routes = dict(zip(ds.lead_times["route"], ds.lead_times["days"]))
    warehouse_leads = warehouse_lead_days(ds.stores, ds.lead_times)
    supply = warehouse_supply(ds.stock_snapshot, issues)
    excluded = {(issue.location_id, issue.sku_id) for issue in issues if issue.excluded}
    protected = set(zip(ds.flagship_protected["store_id"], ds.flagship_protected["style_id"]))
    minimums = min_display_map(ds.min_display)
    receipts = {
        (row.location_id, row.sku_id): row.oldest_stock_received_on
        for row in ds.stock_snapshot.itertuples(index=False)
    }

    results = {
        key: RuleResult(rule=key, label=label, checked=0, passed=True, failures=[])
        for key, label in (
            ("minimum_display", "Minimum display"),
            ("flagship_protection", "Flagship protection"),
            ("capacity", "Store capacity"),
            ("in_transit", "In-transit stock counted once"),
            ("donor_cover", "Donor style cover"),
            ("senior_approval", "Senior approval"),
            ("excluded_pairs", "Data issue exclusions"),
            ("source_stock", "Available source stock"),
            ("ageing", "Ageing eligibility"),
            ("move_details", "Move and route details"),
        )
    }

    def check(rule: str, passed: bool, detail: str) -> None:
        result = results[rule]
        result.checked += 1
        if not passed:
            result.passed = False
            result.failures.append(detail)

    inbound: Counter[Key] = Counter()
    outbound: Counter[Key] = Counter()
    replenishment: Counter[Key] = Counter()
    warehouse_top_ups: Counter[Key] = Counter()
    store_donor_styles: set[Key] = set()
    donor_categories: set[Key] = set()
    ids = Counter(move.id for move in moves)
    move_routes = {(move.from_location, move.to_location, move.sku_id) for move in moves}
    for move in moves:
        source, destination, sku = move.from_location, move.to_location, move.sku_id
        item = items.get(sku)
        check("excluded_pairs", (source, sku) not in excluded and (destination, sku) not in excluded,
              f"{move.id} touches an excluded stock row.")
        if item is not None:
            value = move.units * item.mrp
            check("senior_approval", move.needs_senior_approval == (value > SENIOR_APPROVAL_MRP),
                  f"{move.id} has the wrong senior approval flag for Rs {value:,.0f} at MRP.")

        source_known = source == WAREHOUSE_ID or source in stores
        destination_known = destination == WAREHOUSE_ID or destination in stores
        if not (source_known and destination_known and source != destination and item is not None):
            check("move_details", False, f"{move.id} has an unknown SKU or invalid endpoints.")
            continue

        if source == WAREHOUSE_ID:
            expected_type, lead = "warehouse_to_store", warehouse_leads[destination]
        elif destination == WAREHOUSE_ID:
            expected_type, lead = "pull_back", warehouse_leads[source]
        else:
            expected_type = "store_to_store"
            lead = store_transfer_lead_days(stores[source], stores[destination], routes)

        check("move_details",
              ids[move.id] == 1 and move.type == expected_type and move.units > 0
              and move.style_id == item.style_id and move.category == item.category and move.size == item.size
              and move.value_mrp == move.units * item.mrp
              and bool(move.reason.strip())
              and (expected_type != "store_to_store" or (destination, source, sku) not in move_routes)
              and move.lead_days == lead and move.arrives_on == today + timedelta(days=int(lead)),
              f"{move.id} has an incorrect identity, product, value, route, reason, or arrival date.")
        inbound[destination, sku] += move.units
        outbound[source, sku] += move.units

        if source in stores:
            source_style = (source, item.style_id)
            check("flagship_protection", stores[source].tier != "S++" or source_style not in protected,
                  f"{move.id} takes protected style {item.style_id} from {source}.")
            donor_categories.add((source, display_category(item.category)))
            if destination in stores:
                store_donor_styles.add(source_style)

        ageing = move.id.startswith("age-")
        if ageing:
            row = rows.get((source, sku))
            received = receipts.get((source, sku))
            check("ageing", bool(
                row is not None and received and (today - received).days > AGEING_MIN_AGE_DAYS
                and ageing_cover_reason(row, row.on_hand + row.in_transit)
            ), f"{move.id} does not meet the ageing and cover thresholds.")
        # Ageing consolidations serve a separate purpose from filling a replenishment target.
        if source == WAREHOUSE_ID or (destination in stores and not ageing):
            replenishment[destination, sku] += move.units
        if source == WAREHOUSE_ID:
            warehouse_top_ups[destination, sku] += move.units

    for (source, sku), units in sorted(outbound.items()):
        row = rows.get((source, sku))
        available = supply.get(sku, 0) if source == WAREHOUSE_ID else (row.on_hand if row else 0)
        check("source_stock", units <= available,
              f"{source} sends {units} of {sku} but has only {available} on hand.")

    current_category: Counter[Key] = Counter()
    donor_category: Counter[Key] = Counter()
    current_store: Counter[str] = Counter()
    receipts_by_store: Counter[str] = Counter()
    donor_style: Counter[Key] = Counter()
    style_forecast: dict[Key, float] = defaultdict(float)
    for (store, sku), row in rows.items():
        current = row.on_hand + row.in_transit
        remaining = current - outbound[store, sku]
        category = (store, display_category(row.category))
        style = (store, row.style_id)
        current_store[store] += current
        current_category[category] += current
        donor_category[category] += remaining
        donor_style[style] += remaining
        style_forecast[style] += float(row.forecast_daily)

    for (store, sku), units in sorted(inbound.items()):
        receipts_by_store[store] += units
        check("excluded_pairs", store == WAREHOUSE_ID or (store, sku) in rows,
              f"{store} cannot receive SKU {sku} from an unavailable stock pair.")

    # Warehouse display top-ups may exceed a SKU's forecast target by the initial category gap.
    display_over_target: Counter[Key] = Counter()
    for (store, sku), units in sorted(replenishment.items()):
        row = rows.get((store, sku))
        if row is None:
            continue
        excess = max(0, units - row.need)
        warehouse_excess = max(0, warehouse_top_ups[store, sku] - row.need)
        check("in_transit", excess <= warehouse_excess,
              f"{store} receives {units} of {sku} for a net need of {row.need} after transit.")
        display_over_target[store, display_category(row.category)] += warehouse_excess
    for (store, category), units in sorted(display_over_target.items()):
        minimum = minimums.get((stores[store].tier, category), 0)
        gap = max(0, minimum - current_category[store, category])
        check("in_transit", units <= gap,
              f"{store} receives {units} extra {category} units against a display gap of {gap}.")

    # Any combination of approvals must fit, even without its offsetting moves.
    for store, row in sorted(stores.items()):
        room = max(0, row.stock_capacity_units - current_store[store])
        units = receipts_by_store[store]
        check("capacity", units <= room,
              f"{store} receives {units} units against {room} units of snapshot headroom.")

    for store, category in sorted(donor_categories):
        minimum = minimums.get((stores[store].tier, category), 0)
        remaining = donor_category[store, category]
        check("minimum_display", remaining >= minimum,
              f"{store} keeps {remaining} {category} units without pending receipts, against a minimum of {minimum}.")

    for store, style in sorted(store_donor_styles):
        stock = donor_style[store, style]
        required = DONOR_MIN_COVER_DAYS * style_forecast[store, style]
        check("donor_cover", stock >= required,
              f"{store} keeps {stock} units of {style} without pending receipts and needs {required:.2f} for 30 days of cover.")

    return list(results.values())
