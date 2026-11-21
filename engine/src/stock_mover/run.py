"""Build one run: data checks, demand, warehouse allocation and the contract file."""

from collections.abc import Callable
from datetime import datetime, timezone

from stock_mover.allocate import (
    add_targets,
    allocate,
    store_headroom,
    warehouse_lead_days,
    warehouse_moves,
    warehouse_supply,
)
from stock_mover.briefing import Facts, build_facts, format_inr
from stock_mover.checks import find_data_issues
from stock_mover.constants import TODAY
from stock_mover.contract import Briefing, DataIssue, Move, Run, RunInfo
from stock_mover.demand import build_demand
from stock_mover.health import store_health
from stock_mover.loader import Dataset
from stock_mover.store_moves import plan_store_moves
from stock_mover.validate import RuleViolation, validate_moves

Trigger = str  # "manual" | "schedule" | "seed", validated by RunInfo


def template_briefing(moves: list[Move], issues: list[DataIssue]) -> Briefing:
    units = sum(m.units for m in moves)
    value = sum(m.value_mrp for m in moves)
    senior = sum(m.needs_senior_approval for m in moves)
    excluded = sum(i.excluded for i in issues)
    text = (
        f"Today's list has {len(moves)} stock moves, {units} units worth Rs {format_inr(value)} at MRP. "
        f"{senior} of them need senior approval. "
        f"{excluded} data issues were found and left out of every move."
    )
    return Briefing(text=text, source="template", checked=True)


def build_run(
    ds: Dataset,
    now: datetime,
    trigger: Trigger,
    briefing_writer: Callable[[Facts, Briefing], Briefing] | None = None,
) -> Run:
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
    moves.extend(plan_store_moves(table, alloc, ds, TODAY, issues))
    moves.sort(key=lambda move: (-move.priority, move.id))
    rules = validate_moves(moves, table, ds, issues, TODAY)
    failures = [f"{rule.label}: {detail}" for rule in rules for detail in rule.failures]
    if failures:
        raise RuleViolation("Rule validation failed.\n" + "\n".join(failures))
    run = Run(
        run=RunInfo(
            id=f"{TODAY.isoformat()}-{generated_at:%Y%m%dT%H%M%SZ}",
            data_as_of=TODAY,
            generated_at=generated_at,
            trigger=trigger,
        ),
        briefing=template_briefing(moves, issues),
        moves=moves,
        rule_check=rules,
        data_issues=issues,
        stores=store_health(table, ds, moves),
    )
    if briefing_writer is not None:
        run.briefing = briefing_writer(build_facts(run), run.briefing)
    return run


def run_text(run: Run) -> str:
    return run.model_dump_json(by_alias=True, indent=2) + "\n"
