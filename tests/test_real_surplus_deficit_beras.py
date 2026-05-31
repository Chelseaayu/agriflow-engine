"""
Tests for sample_data/surplus_deficit_real.csv — BPS real per-kabupaten beras data.

Coverage:
  1. All 38 Jatim kabupaten/kota are mapped (name -> kab_id).
  2. Consumption-ton derivation formula is exact:
       konsumsi_ton = kons_kg_per_minggu * 52 * populasi / 1000
  3. net_ton = produksi_ton - konsumsi_ton; role/volume assignments are correct.
  4. Schema of surplus_deficit_real.csv matches surplus_deficit.csv schema.
  5. Only beras_premium and beras_medium appear (no other commodities).
  6. Sanity: known surplus lumbung (Ngawi, Lamongan, Bojonegoro) are SURPLUS.
  7. Sanity: known dense urban kota (Surabaya, Kota Malang) are DEFICIT.
  8. Grade split: premium 60 % / medium 40 % of total volume per kabupaten.
  9. harvest_age_days = 28 for SURPLUS, 0 for DEFICIT (per methodology).
  10. All kab_ids in the real CSV exist in kabupaten_jatim.csv.
"""
import os
import math
import pathlib

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = pathlib.Path(__file__).parent.parent
REAL_CSV   = ROOT / "sample_data" / "surplus_deficit_real.csv"
SCHEMA_CSV = ROOT / "sample_data" / "surplus_deficit.csv"
KAB_CSV    = ROOT / "sample_data" / "kabupaten_jatim.csv"
BPS_DIR    = ROOT / "sample_data" / "bps_real"

PROD_CSV   = BPS_DIR / "year_beras.csv"
KONS_CSV   = BPS_DIR / "week_konsumsi_beras_perkapita.csv"
POP_CSV    = BPS_DIR / "year_populasi_jatim.csv"

YEAR = 2024
PREMIUM_SPLIT = 0.60
MEDIUM_SPLIT  = 0.40
HARVEST_AGE_SURPLUS = 28
HARVEST_AGE_DEFICIT = 0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def kab_df():
    return pd.read_csv(KAB_CSV)


@pytest.fixture(scope="module")
def name_to_id(kab_df):
    """Map BPS full names ('Kabupaten X' / 'Kota X') -> kab_id (int)."""
    mapping = {}
    for _, row in kab_df.iterrows():
        n = row["nama"]
        if n.startswith("Kota "):
            mapping[n] = int(row["kab_id"])
        else:
            mapping["Kabupaten " + n] = int(row["kab_id"])
    return mapping


@pytest.fixture(scope="module")
def prod_2024():
    df = pd.read_csv(PROD_CSV)
    return df[df["tahun"] == YEAR].copy()


@pytest.fixture(scope="module")
def kons_2024():
    df = pd.read_csv(KONS_CSV)
    return df[df["tahun"] == YEAR].copy()


@pytest.fixture(scope="module")
def pop_2024():
    df = pd.read_csv(POP_CSV)
    return df[df["tahun"] == YEAR].copy()


@pytest.fixture(scope="module")
def real_csv():
    return pd.read_csv(REAL_CSV)


# ---------------------------------------------------------------------------
# 1. All 38 kabupaten/kota are mapped (no silent drops)
# ---------------------------------------------------------------------------

def test_mapping_38_kabupaten(prod_2024, kons_2024, pop_2024, name_to_id):
    """All 38 BPS names in each source file must resolve to a kab_id."""
    for label, df, col in [
        ("produksi",  prod_2024, "kabupaten"),
        ("konsumsi",  kons_2024, "kabupaten/kota"),
        ("populasi",  pop_2024,  "kabupaten/kota"),
    ]:
        unmatched = [n for n in df[col] if n not in name_to_id]
        assert unmatched == [], (
            f"{label}: unmatched names: {unmatched}"
        )
        assert len(df) == 38, (
            f"{label} year {YEAR}: expected 38 rows, got {len(df)}"
        )


# ---------------------------------------------------------------------------
# 2. Consumption-ton formula exactness (spot-check Surabaya)
# ---------------------------------------------------------------------------

def test_konsumsi_ton_formula_surabaya(kons_2024, pop_2024, name_to_id):
    """
    konsumsi_ton = avg_kons_perkapita_kg_per_minggu * 52 * populasi / 1000
    Spot-check Kota Surabaya (kab_id 3578) — expected large deficit.
    """
    kab_id = 3578
    reverse_map = {v: k for k, v in name_to_id.items()}
    raw_name = reverse_map[kab_id]  # 'Kota Surabaya'

    kons_row = kons_2024[kons_2024["kabupaten/kota"] == raw_name]
    pop_row  = pop_2024[pop_2024["kabupaten/kota"]   == raw_name]
    assert len(kons_row) == 1, f"No konsumsi row for {raw_name}"
    assert len(pop_row)  == 1, f"No populasi row for {raw_name}"

    kg_per_week = float(kons_row["avg_konsumsi_perkapita_kg"].iloc[0])
    populasi    = float(pop_row["populasi"].iloc[0])
    expected_kons_ton = kg_per_week * 52 * populasi / 1000
    assert expected_kons_ton > 0
    # Surabaya population ~2.9M, ~1.326 kg/week -> ~199k ton/year
    assert 150_000 < expected_kons_ton < 250_000, (
        f"Surabaya konsumsi_ton out of plausible range: {expected_kons_ton:.0f}"
    )


# ---------------------------------------------------------------------------
# 3. net_ton and role correctness (spot-check Lamongan SURPLUS, Surabaya DEFICIT)
# ---------------------------------------------------------------------------

def test_net_ton_lamongan_surplus(prod_2024, kons_2024, pop_2024, name_to_id):
    """Kabupaten Lamongan must be SURPLUS with large net_ton."""
    raw_name = "Kabupaten Lamongan"
    kab_id   = name_to_id[raw_name]
    assert kab_id == 3524

    prod = float(prod_2024[prod_2024["kabupaten"] == raw_name]["produksi"].iloc[0])
    kons_kg = float(kons_2024[kons_2024["kabupaten/kota"] == raw_name]["avg_konsumsi_perkapita_kg"].iloc[0])
    pop  = float(pop_2024[pop_2024["kabupaten/kota"] == raw_name]["populasi"].iloc[0])
    kons_ton = kons_kg * 52 * pop / 1000
    net = prod - kons_ton
    assert net > 200_000, f"Lamongan net_ton should be >> 200k, got {net:.0f}"


def test_net_ton_surabaya_deficit(prod_2024, kons_2024, pop_2024, name_to_id):
    """Kota Surabaya must be DEFICIT with large absolute net_ton."""
    raw_name = "Kota Surabaya"
    kab_id   = name_to_id[raw_name]
    assert kab_id == 3578

    prod = float(prod_2024[prod_2024["kabupaten"] == raw_name]["produksi"].iloc[0])
    kons_kg = float(kons_2024[kons_2024["kabupaten/kota"] == raw_name]["avg_konsumsi_perkapita_kg"].iloc[0])
    pop  = float(pop_2024[pop_2024["kabupaten/kota"] == raw_name]["populasi"].iloc[0])
    kons_ton = kons_kg * 52 * pop / 1000
    net = prod - kons_ton
    assert net < -100_000, f"Surabaya net_ton should be << -100k, got {net:.0f}"


# ---------------------------------------------------------------------------
# 4. Schema: surplus_deficit_real.csv must match surplus_deficit.csv columns
# ---------------------------------------------------------------------------

def test_schema_matches_canonical(real_csv):
    """Column names and dtypes must match the engine's canonical surplus_deficit.csv."""
    canonical = pd.read_csv(SCHEMA_CSV)
    assert list(real_csv.columns) == list(canonical.columns), (
        f"Column mismatch.\n  real:      {list(real_csv.columns)}\n"
        f"  canonical: {list(canonical.columns)}"
    )


# ---------------------------------------------------------------------------
# 5. Only beras commodities present
# ---------------------------------------------------------------------------

def test_only_beras_commodities(real_csv):
    """surplus_deficit_real.csv must contain only beras_premium and beras_medium."""
    codes = set(real_csv["commodity_code"].unique())
    assert codes == {"beras_premium", "beras_medium"}, (
        f"Unexpected commodity codes: {codes}"
    )


# ---------------------------------------------------------------------------
# 6 & 7. Sanity: known lumbung padi SURPLUS; dense kota DEFICIT
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kab_id,name", [
    (3521, "Ngawi"),
    (3524, "Lamongan"),
    (3522, "Bojonegoro"),
    (3523, "Tuban"),
])
def test_lumbung_padi_surplus(real_csv, kab_id, name):
    """Major paddy-belt kabupaten must be SURPLUS for both grades."""
    rows = real_csv[real_csv["kab_id"] == kab_id]
    assert len(rows) == 2, f"{name} (kab_id={kab_id}) should have 2 rows (premium+medium)"
    for _, row in rows.iterrows():
        assert row["role"] == "SURPLUS", (
            f"{name} {row['commodity_code']} should be SURPLUS, got {row['role']}"
        )
        assert row["volume_tons"] > 50_000, (
            f"{name} {row['commodity_code']} volume should be >> 50k ton"
        )


@pytest.mark.parametrize("kab_id,name", [
    (3578, "Kota Surabaya"),
    (3573, "Kota Malang"),
    (3515, "Sidoarjo"),
])
def test_dense_kota_deficit(real_csv, kab_id, name):
    """Dense urban centres must be DEFICIT for both grades."""
    rows = real_csv[real_csv["kab_id"] == kab_id]
    assert len(rows) == 2, f"{name} (kab_id={kab_id}) should have 2 rows"
    for _, row in rows.iterrows():
        assert row["role"] == "DEFICIT", (
            f"{name} {row['commodity_code']} should be DEFICIT, got {row['role']}"
        )


# ---------------------------------------------------------------------------
# 8. Grade split: premium = 60%, medium = 40% of total volume per kab
# ---------------------------------------------------------------------------

def test_grade_split_ratio(real_csv):
    """
    For every kabupaten, premium_volume / (premium + medium) == 0.60 (within float tolerance).
    """
    for kab_id, grp in real_csv.groupby("kab_id"):
        prem = grp[grp["commodity_code"] == "beras_premium"]["volume_tons"].sum()
        med  = grp[grp["commodity_code"] == "beras_medium"]["volume_tons"].sum()
        total = prem + med
        assert total > 0, f"kab_id {kab_id} has zero volume"
        ratio = prem / total
        assert abs(ratio - PREMIUM_SPLIT) < 1e-3, (
            f"kab_id {kab_id}: premium split = {ratio:.4f}, expected {PREMIUM_SPLIT}"
        )


# ---------------------------------------------------------------------------
# 9. harvest_age_days values
# ---------------------------------------------------------------------------

def test_harvest_age_surplus_rows(real_csv):
    """All SURPLUS rows must have harvest_age_days == 28."""
    surplus = real_csv[real_csv["role"] == "SURPLUS"]
    bad = surplus[surplus["harvest_age_days"] != HARVEST_AGE_SURPLUS]
    assert bad.empty, f"SURPLUS rows with wrong harvest_age_days:\n{bad}"


def test_harvest_age_deficit_rows(real_csv):
    """All DEFICIT rows must have harvest_age_days == 0."""
    deficit = real_csv[real_csv["role"] == "DEFICIT"]
    bad = deficit[deficit["harvest_age_days"] != HARVEST_AGE_DEFICIT]
    assert bad.empty, f"DEFICIT rows with wrong harvest_age_days:\n{bad}"


# ---------------------------------------------------------------------------
# 10. All kab_ids in real CSV exist in kabupaten_jatim.csv
# ---------------------------------------------------------------------------

def test_all_kab_ids_known(real_csv, kab_df):
    """Every kab_id in surplus_deficit_real.csv must be in kabupaten_jatim.csv."""
    known_ids = set(kab_df["kab_id"].astype(int))
    csv_ids   = set(real_csv["kab_id"].astype(int))
    unknown = csv_ids - known_ids
    assert unknown == set(), f"Unknown kab_ids in real CSV: {unknown}"


# ---------------------------------------------------------------------------
# Extra: exactly 38 distinct kabupaten, 76 rows (38 * 2 grades)
# ---------------------------------------------------------------------------

def test_row_count(real_csv):
    """76 rows = 38 kabupaten * 2 grades."""
    assert len(real_csv) == 76, f"Expected 76 rows, got {len(real_csv)}"


def test_kabupaten_count(real_csv):
    """Exactly 38 distinct kab_ids."""
    assert real_csv["kab_id"].nunique() == 38, (
        f"Expected 38 distinct kab_ids, got {real_csv['kab_id'].nunique()}"
    )


# ---------------------------------------------------------------------------
# Extra: volume_tons > 0 everywhere; price > 0 everywhere
# ---------------------------------------------------------------------------

def test_volume_positive(real_csv):
    assert (real_csv["volume_tons"] > 0).all(), "Some volume_tons <= 0"


def test_price_positive(real_csv):
    assert (real_csv["price_idr_per_kg"] > 0).all(), "Some price_idr_per_kg <= 0"
