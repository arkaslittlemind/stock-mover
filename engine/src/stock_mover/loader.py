"""Load the Manyavar CSVs as text and convert the columns the engine uses."""

from dataclasses import dataclass, fields
from pathlib import Path

import pandas as pd

from stock_mover.constants import RAW_DIR

INT_COLUMNS: dict[str, list[str]] = {
    "items": ["mrp", "cost_price", "is_core_style", "is_packaging"],
    "stores": ["size_sqft", "stock_capacity_units"],
    "stock_snapshot": ["on_hand", "in_transit"],
    "stock_weekly": ["closing_on_hand", "days_in_stock"],
    "bill_lines": ["qty", "mrp", "selling_price"],
    "warehouse_inbound": ["qty"],
    "min_display": ["min_display_units"],
    "lead_times": ["days"],
    "flagship_protected": ["rank"],
    "calendar": ["is_wedding_date"],
    "area_managers": ["max_alerts_per_week"],
}

DATE_COLUMNS: dict[str, list[str]] = {
    "stores": ["opened_on"],
    "stock_snapshot": ["as_of_date"],
    "stock_weekly": ["week_ending"],
    "bills": ["bill_date"],
    "warehouse_inbound": ["expected_date"],
    "calendar": ["date"],
}

OPTIONAL_DATE_COLUMNS: dict[str, list[str]] = {
    # Packaging rows have no launch date; they are dropped after loading.
    "items": ["launch_date"],
    "stock_snapshot": ["in_transit_arrives_on", "oldest_stock_received_on"],
}

SKU_KEYED_TABLES = ("bill_lines", "stock_snapshot", "stock_weekly", "warehouse_inbound")

# Hashed customer ids are personal data the engine never needs.
DROPPED_COLUMNS: dict[str, list[str]] = {"bills": ["customer_id"]}


@dataclass(frozen=True)
class Dataset:
    area_managers: pd.DataFrame
    bill_lines: pd.DataFrame
    bills: pd.DataFrame
    calendar: pd.DataFrame
    data_dictionary: pd.DataFrame
    flagship_protected: pd.DataFrame
    footfall_daily: pd.DataFrame
    items: pd.DataFrame
    lead_times: pd.DataFrame
    min_display: pd.DataFrame
    roster_daily: pd.DataFrame
    rules: pd.DataFrame
    salespeople: pd.DataFrame
    stock_snapshot: pd.DataFrame
    stock_weekly: pd.DataFrame
    stores: pd.DataFrame
    warehouse_inbound: pd.DataFrame


def _require_columns(name: str, df: pd.DataFrame, columns: list[str]) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"{name}.csv is missing column(s): {', '.join(missing)}")


def _to_int(name: str, df: pd.DataFrame, column: str) -> pd.Series:
    values = df[column].str.strip()
    bad = values[~values.str.fullmatch(r"-?\d+")]
    if not bad.empty:
        raise ValueError(f"{name}.csv column {column} has a non-integer value: {bad.iloc[0]!r}")
    return values.astype("int64")


def _to_date(name: str, df: pd.DataFrame, column: str, optional: bool = False) -> pd.Series:
    values = df[column].str.strip()
    present = values != ""
    if not optional and not present.all():
        raise ValueError(f"{name}.csv column {column} has an empty value")
    parsed = pd.to_datetime(values[present], format="%Y-%m-%d", errors="coerce")
    if parsed.isna().any():
        bad = values[present][parsed.isna()].iloc[0]
        raise ValueError(f"{name}.csv column {column} has an invalid date: {bad!r}")
    result = pd.Series([None] * len(values), index=values.index, dtype=object)
    result[present] = parsed.dt.date
    return result


def _read_table(raw_dir: Path, name: str) -> pd.DataFrame:
    path = raw_dir / f"{name}.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Missing input file: {path}")
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    ints = INT_COLUMNS.get(name, [])
    dates = DATE_COLUMNS.get(name, [])
    optional_dates = OPTIONAL_DATE_COLUMNS.get(name, [])
    _require_columns(name, df, ints + dates + optional_dates)
    for column in ints:
        df[column] = _to_int(name, df, column)
    for column in dates:
        df[column] = _to_date(name, df, column)
    for column in optional_dates:
        df[column] = _to_date(name, df, column, optional=True)
    return df.drop(columns=DROPPED_COLUMNS.get(name, []), errors="ignore")


def _drop_packaging(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    items = tables["items"]
    packaging = set(items.loc[items["is_packaging"] == 1, "sku_id"])
    tables["items"] = items[items["is_packaging"] == 0].reset_index(drop=True)
    for name in SKU_KEYED_TABLES:
        df = tables[name]
        tables[name] = df[~df["sku_id"].isin(packaging)].reset_index(drop=True)
    return tables


def load_data(raw_dir: Path = RAW_DIR) -> Dataset:
    """Load every CSV in the data pack with packaging SKUs removed."""
    tables = {f.name: _read_table(raw_dir, f.name) for f in fields(Dataset)}
    for name in SKU_KEYED_TABLES + ("items",):
        _require_columns(name, tables[name], ["sku_id"])
    return Dataset(**_drop_packaging(tables))
