"""tests/test_refresh_prices.py -- idempotent, validated price appends."""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.refresh_prices import _validate, append_rows, rows_from_live  # noqa: E402


def _seed(tmp_path: Path) -> Path:
    d = tmp_path / "price_history"
    d.mkdir()
    with (d / "cabe_rawit_cleaned.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "city_id", "commodity_code", "price_per_kg"])
        w.writerow(["2025-12-31", "3578", "cabe_rawit", 43750])
    return d


def test_append_is_idempotent_and_ordered(tmp_path):
    d = _seed(tmp_path)
    rows = _validate([
        {"date": "2026-01-02", "city_id": "3578", "commodity_code": "cabai_rawit", "price_per_kg": "44000"},
        {"date": "2026-01-01", "city_id": "3578", "commodity_code": "cabai_rawit", "price_per_kg": "43900"},
        {"date": "2025-12-31", "city_id": "3578", "commodity_code": "cabai_rawit", "price_per_kg": "43750"},  # dup
        {"date": "2026-01-01", "city_id": "9999", "commodity_code": "cabai_rawit", "price_per_kg": "1"},      # non-IHK
        {"date": "2026-01-01", "city_id": "3578", "commodity_code": "kentang", "price_per_kg": "1"},          # untracked
    ])
    added = append_rows(rows, price_dir=d)
    assert added == {"cabe_rawit_cleaned.csv": 2}
    lines = (d / "cabe_rawit_cleaned.csv").read_text().strip().splitlines()
    assert lines[-2:] == ["2026-01-01,3578,cabe_rawit,43900", "2026-01-02,3578,cabe_rawit,44000"]
    # second run adds nothing
    assert append_rows(rows, price_dir=d) == {"cabe_rawit_cleaned.csv": 0}
    assert len((d / "cabe_rawit_cleaned.csv").read_text().strip().splitlines()) == 4


def test_dry_run_writes_nothing(tmp_path):
    d = _seed(tmp_path)
    rows = _validate([{"date": "2026-01-01", "city_id": "3578", "commodity_code": "cabe_rawit", "price_per_kg": 1000}])
    assert append_rows(rows, price_dir=d, dry_run=True) == {"cabe_rawit_cleaned.csv": 1}
    assert len((d / "cabe_rawit_cleaned.csv").read_text().strip().splitlines()) == 2


def test_validate_rejects_bad_rows():
    with pytest.raises(ValueError):
        _validate([{"date": "not-a-date", "city_id": "3578", "commodity_code": "cabe_rawit", "price_per_kg": 1}])
    with pytest.raises(ValueError):
        _validate([{"date": "2026-01-01", "city_id": "3578", "commodity_code": "cabe_rawit", "price_per_kg": -5}])


def test_live_refuses_mock_rows(monkeypatch):
    """The placeholder scraper falls back to mock; nothing may be written then."""
    import data_sources.pihps_bi as pihps

    class FakeConn:
        def __init__(self, *a, **k): pass
        def fetch_today(self):
            return [{"kabupaten_id": "3578", "commodity_code": "cabai_rawit",
                     "price_per_kg": 1.0, "source": "PIHPS_MOCK"}]

    monkeypatch.setattr(pihps, "PIHPSConnector", FakeConn)
    assert rows_from_live() == []
