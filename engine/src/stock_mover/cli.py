import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from stock_mover.constants import OUT_PATH, SCHEMA_PATH
from stock_mover.contract import run_json_schema
from stock_mover.loader import load_data
from stock_mover.run import build_run, run_text
from stock_mover.validate import RuleViolation


def schema_text() -> str:
    return json.dumps(run_json_schema(), indent=2) + "\n"


def write_schema(out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(schema_text(), encoding="utf-8", newline="\n")


def write_run(out: Path, trigger: str) -> None:
    run = build_run(load_data(), datetime.now(timezone.utc), trigger)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(run_text(run), encoding="utf-8", newline="\n")
    print(f"Wrote {out}: {len(run.moves)} moves, {len(run.data_issues)} data issues")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="stock-mover")
    commands = parser.add_subparsers(dest="command", required=True)
    schema = commands.add_parser("schema", help="write the run JSON Schema for the web app")
    schema.add_argument("--out", type=Path, default=SCHEMA_PATH)
    run = commands.add_parser("run", help="run the engine and write the run JSON")
    run.add_argument("--out", type=Path, default=OUT_PATH)
    run.add_argument("--trigger", choices=["manual", "schedule", "seed"], default="manual")
    args = parser.parse_args(argv)
    if args.command == "schema":
        write_schema(args.out)
        print(f"Wrote {args.out}")
    elif args.command == "run":
        try:
            write_run(args.out, args.trigger)
        except RuleViolation as error:
            parser.exit(1, f"{error}\n")
