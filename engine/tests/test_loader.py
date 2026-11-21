import shutil
from datetime import date
from pathlib import Path

import pytest

from stock_mover.constants import RAW_DIR
from stock_mover.loader import SKU_KEYED_TABLES, load_data


@pytest.fixture(scope="module")
def ds():
    return load_data()


@pytest.fixture
def raw_copy(tmp_path: Path) -> Path:
    small = tmp_path / "raw"
    small.mkdir()
    for path in RAW_DIR.glob("*.csv"):
        if path.name in {"bill_lines.csv", "bills.csv"}:
            lines = path.read_text(encoding="utf-8").splitlines()[:50]
            (small / path.name).write_text("\n".join(lines) + "\n", encoding="utf-8")
        else:
            shutil.copy(path, small / path.name)
    return small


def test_real_data_has_typed_columns(ds):
    assert ds.stock_snapshot["on_hand"].dtype == "int64"
    assert ds.stock_weekly["days_in_stock"].dtype == "int64"
    assert ds.stores["stock_capacity_units"].dtype == "int64"
    assert isinstance(ds.stock_snapshot["as_of_date"].iloc[0], date)
    assert isinstance(ds.stores["opened_on"].iloc[0], date)


def test_optional_dates_allow_blanks(ds):
    arrives = ds.stock_snapshot["in_transit_arrives_on"]
    assert arrives.isna().any()
    assert all(isinstance(v, date) for v in arrives.dropna())


def test_packaging_dropped_everywhere(ds):
    assert (ds.items["is_packaging"] == 0).all()
    raw_items = (RAW_DIR / "items.csv").read_text(encoding="utf-8")
    packaging = {
        line.split(",")[0] for line in raw_items.splitlines()[1:] if line.endswith(",1")
    }
    assert packaging, "fixture expects packaging SKUs in the raw data"
    for name in SKU_KEYED_TABLES:
        assert not getattr(ds, name)["sku_id"].isin(packaging).any(), name


def test_customer_id_never_loaded(ds):
    assert "customer_id" not in ds.bills.columns


def test_missing_file_raises(raw_copy: Path):
    (raw_copy / "stores.csv").unlink()
    with pytest.raises(FileNotFoundError, match="stores.csv"):
        load_data(raw_copy)


def test_missing_column_raises(raw_copy: Path):
    path = raw_copy / "stock_weekly.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace("days_in_stock", "days")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="stock_weekly.csv is missing column.*days_in_stock"):
        load_data(raw_copy)


def test_bad_integer_raises(raw_copy: Path):
    path = raw_copy / "stock_snapshot.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    parts = lines[1].split(",")
    parts[3] = "three"
    lines[1] = ",".join(parts)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="stock_snapshot.csv column on_hand.*'three'"):
        load_data(raw_copy)
