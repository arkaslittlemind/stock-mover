"""The run JSON contract shared with the web app (mirrored there in Zod)."""

from datetime import date
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class RunInfo(Contract):
    id: str
    data_as_of: date
    generated_at: AwareDatetime
    trigger: Literal["manual", "schedule", "seed"]


class Briefing(Contract):
    text: str
    source: Literal["llm", "template"]
    checked: bool


class MoveNumbers(Contract):
    velocity: float
    days_in_stock_84: Annotated[int, Field(ge=0, le=84)]
    # None when forecast demand is 0: JSON has no infinity.
    cover_before: float | None
    cover_after: float | None
    lift: float


class Move(Contract):
    id: str
    type: Literal["warehouse_to_store", "store_to_store", "pull_back"]
    sku_id: str
    style_id: str
    style_name: str
    category: str
    size: str
    from_location: str = Field(alias="from")
    to_location: str = Field(alias="to")
    units: Annotated[int, Field(ge=1)]
    value_mrp: Annotated[float, Field(ge=0)]
    lead_days: Annotated[int, Field(ge=0)]
    arrives_on: date
    priority: float
    reason: str
    needs_senior_approval: bool
    numbers: MoveNumbers


class RuleResult(Contract):
    rule: str
    label: str
    checked: Annotated[int, Field(ge=0)]
    passed: bool
    failures: list[str]


DataCheck = Literal["negative_stock", "snapshot_vs_weekly", "unknown_sku", "unknown_location"]


class DataIssue(Contract):
    location_id: str
    sku_id: str
    checks: Annotated[list[DataCheck], Field(min_length=1)]
    note: str
    excluded: bool


class MinDisplayGap(Contract):
    category: str
    min_display_units: int
    units: int
    gap: int


class StoreHealth(Contract):
    store_id: str
    city: str
    zone: str
    tier: str
    capacity_units: int
    units_on_hand: int
    units_in_transit: int
    fill_pct: float
    days_of_cover: float | None
    min_display_gaps: list[MinDisplayGap]
    flags: list[str]


class Run(Contract):
    run: RunInfo
    briefing: Briefing
    moves: list[Move]
    rule_check: list[RuleResult]
    data_issues: list[DataIssue]
    stores: list[StoreHealth]


def run_json_schema() -> dict:
    """JSON Schema of the run file, as written (by alias)."""
    return Run.model_json_schema(by_alias=True, mode="serialization")
