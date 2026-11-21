from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = REPO_ROOT / "data" / "raw"
SCHEMA_PATH = REPO_ROOT / "apps" / "web" / "data" / "run.schema.json"

# "Today" is the close of the data pack's snapshot date.
TODAY = date(2026, 10, 31)
WAREHOUSE_ID = "WH-KOL"
