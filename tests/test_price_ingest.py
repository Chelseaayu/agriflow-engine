"""
tests/test_price_ingest.py — Unit tests for db/price_ingest.py

Covers:
  - All 9 CSVs load without error
  - Schema: each row has exactly the 4 required keys with correct types
  - Date range: 2021 data present, 2025 data present
  - Price values: positive floats
  - Commodity mapping:
      * bawang_merah, bawang_putih, daging_ayam, telur_ayam — direct match
      * cabe_rawit -> cabai_rawit (spelling normalisation)
      * medium1 / medium2 -> beras_medium (grade aggregation)
      * super1 / super2 -> beras_premium (grade aggregation)
  - No unknown commodity codes survive normalisation (all in KNOWN_ENGINE_CODES)
  - latest_prices() returns 2025 dates for all city x commodity pairs present
  - latest_prices() has correct signature: dict[(city_id, commodity_code)] -> float
  - Sub-grade averaging: when two sub-grades map to same canonical (date, city),
    the returned price is the mean (verified against a synthetic fixture)
  - ingest_to_postgres() raises RuntimeError when called with an empty db_url
"""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

# Module under test
from db.price_ingest import (
    COMMODITY_MAP,
    KNOWN_ENGINE_CODES,
    ingest_to_postgres,
    latest_prices,
    load_price_history_csvs,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PRICE_HISTORY_DIR = Path(__file__).parent.parent / "sample_data" / "price_history"

# Expected canonical codes that must appear in the loaded dataset
EXPECTED_CANONICAL_CODES = {
    "bawang_merah",
    "bawang_putih",
    "cabai_rawit",
    "daging_ayam",
    "telur_ayam",
    "beras_medium",
    "beras_premium",
}

# City IDs covered by PIHPS Tier-1 IHK cities
EXPECTED_CITY_IDS = {"3509", "3510", "3529", "3571", "3573", "3574", "3577", "3578"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def loaded_rows():
    """Load all 9 CSVs once per module; share across tests."""
    return load_price_history_csvs(PRICE_HISTORY_DIR)


# ---------------------------------------------------------------------------
# 1. Load integrity
# ---------------------------------------------------------------------------

class TestLoadIntegrity:

    def test_returns_nonempty_list(self, loaded_rows):
        assert isinstance(loaded_rows, list)
        assert len(loaded_rows) > 0, "Expected non-empty row list from 9 CSVs"

    def test_minimum_row_count(self, loaded_rows):
        # 9 CSVs × ~10k rows each. After sub-grade collapsing, still > 50k unique rows.
        assert len(loaded_rows) >= 50_000, (
            f"Expected >= 50,000 rows, got {len(loaded_rows)}"
        )

    def test_all_rows_have_four_keys(self, loaded_rows):
        required = {"date", "city_id", "commodity_code", "price_per_kg"}
        for i, row in enumerate(loaded_rows):
            assert set(row.keys()) == required, (
                f"Row {i} has wrong keys: {set(row.keys())}"
            )

    def test_date_type(self, loaded_rows):
        bad = [r for r in loaded_rows if not isinstance(r["date"], datetime.date)]
        assert not bad, f"Found {len(bad)} rows with non-date date field"

    def test_city_id_type(self, loaded_rows):
        bad = [r for r in loaded_rows if not isinstance(r["city_id"], str)]
        assert not bad, f"Found {len(bad)} rows with non-str city_id"

    def test_commodity_code_type(self, loaded_rows):
        bad = [r for r in loaded_rows if not isinstance(r["commodity_code"], str)]
        assert not bad

    def test_price_per_kg_is_positive_float(self, loaded_rows):
        bad = [r for r in loaded_rows
               if not isinstance(r["price_per_kg"], (int, float))
               or r["price_per_kg"] <= 0]
        assert not bad, f"Found {len(bad)} rows with non-positive or non-numeric price"


# ---------------------------------------------------------------------------
# 2. Date coverage
# ---------------------------------------------------------------------------

class TestDateCoverage:

    def test_2021_data_present(self, loaded_rows):
        years = {r["date"].year for r in loaded_rows}
        assert 2021 in years, "Expected 2021 data to be present"

    def test_2025_data_present(self, loaded_rows):
        years = {r["date"].year for r in loaded_rows}
        assert 2025 in years, "Expected 2025 data to be present"

    def test_all_years_2021_to_2025(self, loaded_rows):
        years = {r["date"].year for r in loaded_rows}
        for yr in range(2021, 2026):
            assert yr in years, f"Missing year {yr} in loaded data"


# ---------------------------------------------------------------------------
# 3. Commodity mapping
# ---------------------------------------------------------------------------

class TestCommodityMapping:

    def test_all_canonical_codes_present(self, loaded_rows):
        codes = {r["commodity_code"] for r in loaded_rows}
        for expected in EXPECTED_CANONICAL_CODES:
            assert expected in codes, f"Expected canonical code {expected!r} not found"

    def test_no_raw_medium_codes_survive(self, loaded_rows):
        """beras_medium_1 and beras_medium_2 must have been normalised away."""
        raw_beras = {"beras_medium_1", "beras_medium_2", "beras_super_1", "beras_super_2"}
        surviving = {r["commodity_code"] for r in loaded_rows} & raw_beras
        assert not surviving, f"Raw PIHPS sub-grade codes survived normalisation: {surviving}"

    def test_no_cabe_rawit_raw_code_survives(self, loaded_rows):
        """cabe_rawit (Chelsea spelling) must be mapped to cabai_rawit."""
        codes = {r["commodity_code"] for r in loaded_rows}
        assert "cabe_rawit" not in codes, (
            "Raw Chelsea code 'cabe_rawit' survived; expected 'cabai_rawit'"
        )
        assert "cabai_rawit" in codes, (
            "'cabai_rawit' not found; normalisation may have failed"
        )

    def test_cabai_rawit_is_not_cabai_merah(self, loaded_rows):
        """These are distinct commodities — must NOT be merged."""
        codes = {r["commodity_code"] for r in loaded_rows}
        # cabai_merah is NOT in the dataset (Chelsea has no cabai_merah file)
        assert "cabai_merah" not in codes, (
            "cabai_merah should not appear — it is not in the PIHPS source files"
        )

    def test_all_codes_are_engine_known(self, loaded_rows):
        """Every commodity_code in loaded data must be in KNOWN_ENGINE_CODES."""
        unknown = {r["commodity_code"] for r in loaded_rows} - KNOWN_ENGINE_CODES
        assert not unknown, f"Unknown engine codes found in loaded data: {unknown}"

    def test_commodity_map_contains_all_raw_codes(self):
        """COMMODITY_MAP must cover all 9 raw codes from Chelsea's files."""
        raw_codes_in_files = {
            "bawang_merah", "bawang_putih", "cabe_rawit",
            "daging_ayam", "telur_ayam",
            "beras_medium_1", "beras_medium_2",
            "beras_super_1", "beras_super_2",
        }
        missing = raw_codes_in_files - set(COMMODITY_MAP.keys())
        assert not missing, f"COMMODITY_MAP missing entries for: {missing}"


# ---------------------------------------------------------------------------
# 4. City coverage
# ---------------------------------------------------------------------------

class TestCityCoverage:

    def test_all_eight_cities_present(self, loaded_rows):
        cities = {r["city_id"] for r in loaded_rows}
        for city in EXPECTED_CITY_IDS:
            assert city in cities, f"Expected city_id {city} not found in loaded data"


# ---------------------------------------------------------------------------
# 5. Sub-grade averaging (synthetic fixture, no filesystem dependency)
# ---------------------------------------------------------------------------

class TestSubGradeAveraging:

    def test_averaging_of_two_subgrades_same_date_city(self, tmp_path):
        """When medium1 and medium2 both have a row for the same (date, city),
        the returned price for beras_medium is their mean."""
        # Write two minimal CSVs
        m1 = tmp_path / "medium1_cleaned.csv"
        m2 = tmp_path / "medium2_cleaned.csv"
        m1.write_text("date,city_id,commodity_code,price_per_kg\n"
                      "2025-01-01,3578,beras_medium_1,10000\n", encoding="utf-8")
        m2.write_text("date,city_id,commodity_code,price_per_kg\n"
                      "2025-01-01,3578,beras_medium_2,12000\n", encoding="utf-8")

        rows = load_price_history_csvs(tmp_path)
        assert len(rows) == 1, f"Expected 1 collapsed row, got {len(rows)}"
        row = rows[0]
        assert row["commodity_code"] == "beras_medium"
        assert row["price_per_kg"] == pytest.approx(11000.0), (
            f"Expected mean of 10000+12000=11000, got {row['price_per_kg']}"
        )

    def test_no_collision_when_different_city(self, tmp_path):
        """When the two sub-grades have different city_ids, no averaging — two rows."""
        m1 = tmp_path / "medium1_cleaned.csv"
        m2 = tmp_path / "medium2_cleaned.csv"
        m1.write_text("date,city_id,commodity_code,price_per_kg\n"
                      "2025-01-01,3578,beras_medium_1,10000\n", encoding="utf-8")
        m2.write_text("date,city_id,commodity_code,price_per_kg\n"
                      "2025-01-01,3509,beras_medium_2,12000\n", encoding="utf-8")

        rows = load_price_history_csvs(tmp_path)
        assert len(rows) == 2, f"Expected 2 rows for 2 different cities, got {len(rows)}"
        codes = {r["commodity_code"] for r in rows}
        assert codes == {"beras_medium"}


# ---------------------------------------------------------------------------
# 6. latest_prices()
# ---------------------------------------------------------------------------

class TestLatestPrices:

    def test_returns_dict(self, loaded_rows):
        result = latest_prices(loaded_rows)
        assert isinstance(result, dict)

    def test_keys_are_tuples_of_two_strings(self, loaded_rows):
        result = latest_prices(loaded_rows)
        for key in list(result.keys())[:20]:  # sample first 20
            assert isinstance(key, tuple) and len(key) == 2
            city_id, commodity_code = key
            assert isinstance(city_id, str)
            assert isinstance(commodity_code, str)

    def test_values_are_positive_floats(self, loaded_rows):
        result = latest_prices(loaded_rows)
        for key, price in list(result.items())[:20]:
            assert isinstance(price, (int, float)) and price > 0, (
                f"latest_prices[{key}] = {price} is not a positive number"
            )

    def test_returns_2025_prices(self, loaded_rows):
        """latest_prices should be sourced from 2025 rows (the latest year)."""
        # Re-run latest_prices but also track dates for spot verification
        best_date: dict = {}
        for row in loaded_rows:
            key = (row["city_id"], row["commodity_code"])
            if key not in best_date or row["date"] > best_date[key]:
                best_date[key] = row["date"]

        result = latest_prices(loaded_rows)
        for key, price in result.items():
            latest_date = best_date[key]
            # The latest date in this dataset is end of 2025
            assert latest_date.year == 2025, (
                f"latest_prices[{key}]: expected date in 2025, got {latest_date}"
            )

    def test_surabaya_bawang_merah_present(self, loaded_rows):
        """Spot-check: Surabaya (3578) x bawang_merah must have a latest price."""
        result = latest_prices(loaded_rows)
        assert ("3578", "bawang_merah") in result, (
            "Expected latest price for (3578, bawang_merah)"
        )
        price = result[("3578", "bawang_merah")]
        # Bawang merah retail in IDR/kg; sanity range 20k-100k
        assert 20_000 <= price <= 100_000, (
            f"Surabaya bawang_merah price {price} outside sanity range 20k-100k"
        )

    def test_surabaya_beras_medium_present(self, loaded_rows):
        """Spot-check: Surabaya (3578) x beras_medium must have a latest price."""
        result = latest_prices(loaded_rows)
        assert ("3578", "beras_medium") in result

    def test_surabaya_beras_premium_present(self, loaded_rows):
        """Spot-check: Surabaya (3578) x beras_premium must have a latest price."""
        result = latest_prices(loaded_rows)
        assert ("3578", "beras_premium") in result

    def test_latest_is_idempotent(self, loaded_rows):
        """Calling latest_prices twice on the same rows gives identical results."""
        r1 = latest_prices(loaded_rows)
        r2 = latest_prices(loaded_rows)
        assert r1 == r2

    def test_synthetic_latest_wins(self, tmp_path):
        """Given two rows for same key, the later date wins."""
        csv_path = tmp_path / "bawang_merah_cleaned.csv"
        csv_path.write_text(
            "date,city_id,commodity_code,price_per_kg\n"
            "2021-06-01,3578,bawang_merah,30000\n"
            "2025-11-15,3578,bawang_merah,45000\n",
            encoding="utf-8",
        )
        rows = load_price_history_csvs(tmp_path)
        result = latest_prices(rows)
        assert result[("3578", "bawang_merah")] == pytest.approx(45000.0)


# ---------------------------------------------------------------------------
# 7. Error paths
# ---------------------------------------------------------------------------

class TestErrorPaths:

    def test_missing_directory_raises(self, tmp_path):
        nonexistent = tmp_path / "does_not_exist"
        with pytest.raises(FileNotFoundError):
            load_price_history_csvs(nonexistent)

    def test_empty_directory_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="No \\*_cleaned.csv files"):
            load_price_history_csvs(tmp_path)

    def test_unknown_commodity_code_raises(self, tmp_path):
        bad_csv = tmp_path / "unknown_cleaned.csv"
        bad_csv.write_text(
            "date,city_id,commodity_code,price_per_kg\n"
            "2025-01-01,3578,gula_aren,25000\n",  # gula_aren not in COMMODITY_MAP
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="unrecognised commodity_code"):
            load_price_history_csvs(tmp_path)

    def test_ingest_to_postgres_raises_without_db_url(self, loaded_rows):
        """ingest_to_postgres must raise RuntimeError when db_url is empty."""
        with pytest.raises(RuntimeError, match="requires an explicit db_url"):
            ingest_to_postgres(loaded_rows[:10], db_url="")

    def test_ingest_to_postgres_raises_with_whitespace_db_url(self, loaded_rows):
        with pytest.raises(RuntimeError, match="requires an explicit db_url"):
            ingest_to_postgres(loaded_rows[:10], db_url="   ")
