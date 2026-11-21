"""Build one run: data checks, demand, warehouse allocation and the contract file."""

from datetime import datetime, timezone

from stock_mover.allocate import (
    add_targets,
    allocate,
    store_headroom,
    warehouse_lead_days,
    warehouse_moves,
    warehouse_supply,
)
from stock_mover.checks import find_data_issues
from stock_mover.constants import TODAY
from stock_mover.contract import Briefing, DataIssue, Move, Run, RunInfo
from stock_mover.demand import build_demand
from stock_mover.loader import Dataset

Trigger = str  # "manual" | "schedule" | "seed", validated by RunInfo


def format_inr(value: float) -> str:
    """Whole rupees with Indian digit grouping: 11393257 -> 1,13,93,257."""
    digits = str(round(value))
    head, tail = digits[:-3], digits[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    return ",".join(([head] if head else []) + groups + [tail])


def template_briefing(moves: list[Move], issues: list[DataIssue]) -> Briefing:
    units = sum(m.units for m in moves)
    value = sum(m.value_mrp for m in moves)
    senior = sum(m.needs_senior_approval for m in moves)
    excluded = sum(i.excluded for i in issues)
    text = (
        f"Today's list has {len(moves)} warehouse-to-store moves, {units} units worth Rs {format_inr(value)} at MRP. "
        f"{senior} of them need senior approval. "
        f"{excluded} data issues were found and left out of every move."
    )
    return Briefing(text=text, source="template", checked=True)


def build_run(ds: Dataset, now: datetime, trigger: Trigger) -> Run:
    """The full run for the data pack; `now` must be timezone-aware."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    generated_at = now.astimezone(timezone.utc)
    issues = find_data_issues(ds)
    demand = build_demand(ds, issues, TODAY)
    table = add_targets(demand.skus, warehouse_lead_days(ds.stores, ds.lead_times))
    alloc = allocate(
        table,
        warehouse_supply(ds.stock_snapshot, issues),
        store_headroom(demand.skus, ds.stores),
        ds.min_display,
    )
    moves = warehouse_moves(table, alloc, ds.items, ds.min_display, TODAY)
    return Run(
        run=RunInfo(
            id=f"{TODAY.isoformat()}-{generated_at:%Y%m%dT%H%M%SZ}",
            data_as_of=TODAY,
            generated_at=generated_at,
            trigger=trigger,
        ),
        briefing=template_briefing(moves, issues),
        moves=moves,
        rule_check=[],
        data_issues=issues,
        stores=[],
    )


def run_text(run: Run) -> str:
    return run.model_dump_json(by_alias=True, indent=2) + "\n"
