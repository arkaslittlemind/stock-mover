import json
from datetime import date, datetime, timedelta, timezone

import jsonschema
import pytest
from pydantic import ValidationError

from stock_mover.cli import main, schema_text
from stock_mover.constants import SCHEMA_PATH
from stock_mover.contract import Run, run_json_schema

IST = timezone(timedelta(hours=5, minutes=30))


def move(move_type: str, idx: int) -> dict:
    return {
        "id": f"m{idx}",
        "type": move_type,
        "sku_id": "KUR-04-L",
        "style_id": "KUR-04",
        "style_name": "Chikankari Kurta Set",
        "category": "Kurta Set",
        "size": "L",
        "from": "WH-KOL",
        "to": "LKO-01",
        "units": 18,
        "value_mrp": 122382.0,
        "lead_days": 4,
        "arrives_on": date(2026, 11, 4),
        "priority": 12.5,
        "reason": "LKO-01 had KUR-04 in stock only 14 of 84 days and still sold 12.",
        "needs_senior_approval": True,
        "numbers": {
            "velocity": 0.86,
            "days_in_stock_84": 14,
            "cover_before": 0.0,
            "cover_after": None,
            "lift": 1.4,
        },
    }


def sample_run() -> Run:
    return Run.model_validate(
        {
            "run": {
                "id": "run-20261031",
                "data_as_of": date(2026, 10, 31),
                "generated_at": datetime(2026, 11, 21, 6, 0, tzinfo=IST),
                "trigger": "seed",
            },
            "briefing": {"text": "Three moves today.", "source": "template", "checked": True},
            "moves": [move(t, i) for i, t in enumerate(["warehouse_to_store", "store_to_store", "pull_back"])],
            "rule_check": [
                {"rule": "capacity", "label": "Store capacity", "checked": 3, "passed": True, "failures": []}
            ],
            "data_issues": [
                {
                    "location_id": "KNP-03",
                    "sku_id": "SHW-02-L",
                    "checks": ["snapshot_vs_weekly"],
                    "note": "Snapshot shows 300 on hand, but the 31 Oct weekly close shows 0.",
                    "excluded": True,
                }
            ],
            "stores": [
                {
                    "store_id": "MZF-01",
                    "city": "Muzaffarpur",
                    "zone": "East",
                    "tier": "A",
                    "capacity_units": 500,
                    "units_on_hand": 185,
                    "units_in_transit": 0,
                    "fill_pct": 37.0,
                    "days_of_cover": 29.0,
                    "min_display_gaps": [
                        {"category": "Mojari", "min_display_units": 30, "units": 12, "gap": 18}
                    ],
                    "flags": ["under-stocked"],
                }
            ],
        }
    )


def dumped() -> dict:
    return sample_run().model_dump(mode="json", by_alias=True)


def test_sample_run_validates_against_exported_schema():
    jsonschema.validate(dumped(), run_json_schema())


def test_moves_use_from_and_to_keys():
    first = dumped()["moves"][0]
    assert first["from"] == "WH-KOL" and first["to"] == "LKO-01"
    assert "from_location" not in first and "to_location" not in first


def test_dump_round_trips():
    data = dumped()
    assert Run.model_validate(data).model_dump(mode="json", by_alias=True) == data


@pytest.mark.parametrize(
    "path, value",
    [(("moves", 0, "type"), "teleport"), (("run", "trigger"), "cron")],
)
def test_unknown_enum_values_rejected(path, value):
    data = dumped()
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValidationError):
        Run.model_validate(data)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, run_json_schema())


def test_committed_schema_matches_models():
    assert SCHEMA_PATH.read_text(encoding="utf-8") == schema_text()


def test_schema_command_writes_file(tmp_path):
    out = tmp_path / "run.schema.json"
    main(["schema", "--out", str(out)])
    assert json.loads(out.read_text(encoding="utf-8")) == run_json_schema()
