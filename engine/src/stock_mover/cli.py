import argparse
import json
from pathlib import Path

from stock_mover.constants import SCHEMA_PATH
from stock_mover.contract import run_json_schema


def schema_text() -> str:
    return json.dumps(run_json_schema(), indent=2) + "\n"


def write_schema(out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(schema_text(), encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="stock-mover")
    commands = parser.add_subparsers(dest="command", required=True)
    schema = commands.add_parser("schema", help="write the run JSON Schema for the web app")
    schema.add_argument("--out", type=Path, default=SCHEMA_PATH)
    args = parser.parse_args(argv)
    if args.command == "schema":
        write_schema(args.out)
        print(f"Wrote {args.out}")
