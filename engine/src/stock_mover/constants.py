from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = REPO_ROOT / "data" / "raw"
SCHEMA_PATH = REPO_ROOT / "apps" / "web" / "data" / "run.schema.json"

# "Today" is the close of the data pack's snapshot date.
TODAY = date(2026, 10, 31)
WAREHOUSE_ID = "WH-KOL"

# Demand rules (project plan, engine steps 2 to 4).
VELOCITY_WINDOW_DAYS = 84
PEER_MIN_DAYS_IN_STOCK = 14
NEW_STORE_DAYS = 60
NEW_STYLE_DAYS = 30
LIFT_AFTER_DAYS = 30
LIFT_MIN = 1.0
LIFT_MAX = 3.0
