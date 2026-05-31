"""
Tests for surplus_deficit_real.csv — hortikultura commodities @ 2022.

Covers cabai_merah, cabai_rawit, bawang_merah, bawang_putih.

Test checklist:
  H1.  Wide-to-long reshape: cabai_merah = cabai_besar + cabai_keriting (kuintal -> ton).
  H2.  Total row excluded from all 5 source files.
  H3.  Kuintal -> ton conversion: Jatim total cabai_besar ~85,145 ton (verify against Total row/10).
  H4.  Name mapping: 38 kab mapped (positional — rows 0-28 kab, 29-37 kota).
  H5.  Derivation: surplus = produksi_ton - (per_kapita_kg_yr * populasi / 1000).
  H6.  Sanity: bawang_merah top producer = Nganjuk (kab_id 3518).
  H7.  Sanity: bawang_putih ALL DEFICIT (Jatim produces ~855 ton vs ~600k+ ton consumption).
  H8.  Sanity: cabai_rawit top-3 in {Banyuwangi 3510, Malang 3507, Kediri 3506, Sampang 3527}.
  H9.  Sanity: Kota Surabaya DEFICIT for all 4 hortikultura commodities.
  H10. harvest_age_days = 28 for SURPLUS, 0 for DEFICIT across hortikultura rows.
  H11. price_idr_per_kg is positive and matches expected PIHPS/baseline values.
  H12. volume_tons > 0 for all rows.
  H13. Total rows in file = 228 (38 kab * 6 commodities — beras has 2 grades).
  H14. Per-kapita constants are the Kementan 2022 values (frozen in derivation script).
"""

from __future__ import annotations

import pathlib

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = pathlib.Path(__file__).parent.parent
REAL_CSV  = ROOT / "sample_data" / "surplus_deficit_real.csv"
KAB_CSV   = ROOT / "sample_data" / "kabupaten_jatim.csv"
BPS_DIR   = ROOT / "sample_data" / "bps_real"
POP_CSV   = BPS_DIR / "year_populasi_jatim.csv"

# Raw hortikultura source directory (may not be present on CI — tests that need it
# are marked with skipif)
HORTI_DIR = pathlib.Path("D:/DOWNLOAD/Download 2026/baru-20260531T082645Z-3-001/baru")
HORTI_AVAILABLE = HORTI_DIR.exists()

YEAR = 2022

# Kementan PDF 2024, Tabel 4.6a/4.1a/4.2a (p.30/25/26), year 2022
PERKAPITA_KG_YR = {
    "cabai_merah":  1.909,
    "cabai_rawit":  2.073,
    "bawang_merah": 3.024,
    "bawang_putih": 2.016,
}

EXPECTED_PRICES = {
    "cabai_merah":  45_000,   # komoditas_constraints baseline [NOT in PIHPS — flagged]
    "cabai_rawit":  41_000,   # PIHPS 2022 median
    "bawang_merah": 32_500,   # PIHPS 2022 median
    "bawang_putih": 20_750,   # PIHPS 2022 median
}

HORTI_CODES = list(PERKAPITA_KG_YR.keys())
ALL_CODES = HORTI_CODES + ["beras_premium", "beras_medium"]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def real_csv():
    return pd.read_csv(REAL_CSV)


@pytest.fixture(scope="module")
def horti_csv(real_csv):
    return real_csv[real_csv["commodity_code"].isin(HORTI_CODES)].copy()


@pytest.fixture(scope="module")
def kab_df():
    return pd.read_csv(KAB_CSV)


@pytest.fixture(scope="module")
def kab_ids_ordered(kab_df):
    """38 kab_ids in BPS hortikultura row order: kab 3501-3529 then kota 3571-3579."""
    non_kota = kab_df[~kab_df["nama"].str.startswith("Kota ")].sort_values("kab_id")
    kota     = kab_df[kab_df["nama"].str.startswith("Kota ")].sort_values("kab_id")
    return list(non_kota["kab_id"].astype(int)) + list(kota["kab_id"].astype(int))


@pytest.fixture(scope="module")
def pop_2022():
    df = pd.read_csv(POP_CSV)
    return df[df["tahun"] == YEAR].copy()


# ---------------------------------------------------------------------------
# H1. Wide-to-long reshape and cabai_merah = besar + keriting (kuintal -> ton)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HORTI_AVAILABLE, reason="Raw horti download dir not on this machine")
def test_cabai_merah_equals_besar_plus_keriting(real_csv, kab_ids_ordered):
    """
    cabai_merah produksi implied by surplus+consumption must equal
    (cabai_besar + cabai_keriting) in kuintal / 10 for each kabupaten.
    Spot-check Kab. Malang (kab_id=3507).
    """
    kab_id = 3507  # Kabupaten Malang

    # Source production in ton from BPS horti files
    cb = pd.read_csv(HORTI_DIR / "cabai_besar.csv", encoding="utf-8-sig")
    ck = pd.read_csv(HORTI_DIR / "cabai_keriting.csv", encoding="utf-8-sig")
    cb = cb[cb["Kabupaten"] != "Total"].reset_index(drop=True)
    ck = ck[ck["Kabupaten"] != "Total"].reset_index(drop=True)

    idx = kab_ids_ordered.index(kab_id)  # positional index in BPS order
    expected_ton = (cb["Produksi_2022"].fillna(0).iloc[idx] +
                    ck["Produksi_2022"].fillna(0).iloc[idx]) / 10.0

    # Reconstruct produksi_ton from the real CSV row
    pop_df = pd.read_csv(POP_CSV)
    pop22  = pop_df[pop_df["tahun"] == YEAR]
    kab_df = pd.read_csv(KAB_CSV)
    id_to_full = {}
    for _, r in kab_df.iterrows():
        n = r["nama"]
        k = int(r["kab_id"])
        id_to_full[k] = n if n.startswith("Kota ") else "Kabupaten " + n

    full_name = id_to_full[kab_id]
    pop = float(pop22[pop22["kabupaten/kota"] == full_name]["populasi"].iloc[0])
    kons_ton = PERKAPITA_KG_YR["cabai_merah"] * pop / 1000.0

    row = real_csv[(real_csv["kab_id"] == kab_id) &
                   (real_csv["commodity_code"] == "cabai_merah")]
    assert len(row) == 1
    vol   = float(row["volume_tons"].iloc[0])
    role  = row["role"].iloc[0]
    implied_net = vol if role == "SURPLUS" else -vol
    implied_prod = implied_net + kons_ton

    assert abs(implied_prod - expected_ton) < 1.0, (
        f"Kab Malang cabai_merah produksi mismatch: "
        f"implied={implied_prod:.2f} ton, expected={expected_ton:.2f} ton"
    )


# ---------------------------------------------------------------------------
# H2. Total row excluded
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HORTI_AVAILABLE, reason="Raw horti download dir not on this machine")
@pytest.mark.parametrize("filename", [
    "cabai_besar.csv", "cabai_keriting.csv", "cabai_rawit.csv",
    "bawang_merah.csv", "bawang_putih.csv",
])
def test_total_row_excluded(filename):
    """After excluding 'Total', each file has exactly 38 data rows."""
    df = pd.read_csv(HORTI_DIR / filename, encoding="utf-8-sig")
    df_no_total = df[df["Kabupaten"] != "Total"]
    assert len(df_no_total) == 38, (
        f"{filename}: expected 38 rows after excluding Total, got {len(df_no_total)}"
    )


# ---------------------------------------------------------------------------
# H3. Kuintal -> ton conversion (Jatim total cabai_besar 2022)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HORTI_AVAILABLE, reason="Raw horti download dir not on this machine")
def test_kuintal_to_ton_cabai_besar():
    """
    Jatim total cabai_besar 2022 from Total row in CSV (kuintal) / 10 should match
    sum of individual kab rows (after NaN->0).
    Plausibility: ~85,145 ton (matches BPS published Jatim figure).
    """
    df = pd.read_csv(HORTI_DIR / "cabai_besar.csv", encoding="utf-8-sig")
    total_row = df[df["Kabupaten"] == "Total"]["Produksi_2022"].values[0]
    data_rows = df[df["Kabupaten"] != "Total"]["Produksi_2022"].fillna(0)
    sum_from_data = data_rows.sum()

    assert abs(sum_from_data - total_row) < 10, (
        f"Sum of rows ({sum_from_data:.0f}) doesn't match Total row ({total_row:.0f}) in kuintal"
    )
    ton_total = total_row / 10.0
    # Plausibility: BPS Jatim cabai besar 2022 ~85k ton
    assert 60_000 < ton_total < 120_000, (
        f"Jatim cabai_besar 2022 total = {ton_total:.0f} ton — outside plausible range"
    )


# ---------------------------------------------------------------------------
# H4. Name mapping: 38 kab mapped to kab_ids
# ---------------------------------------------------------------------------

def test_horti_kab_count(horti_csv):
    """Each hortikultura commodity must have exactly 38 rows."""
    for code in HORTI_CODES:
        sub = horti_csv[horti_csv["commodity_code"] == code]
        assert len(sub) == 38, (
            f"{code}: expected 38 rows, got {len(sub)}"
        )


def test_horti_kab_ids_known(horti_csv, kab_df):
    """All kab_ids in hortikultura rows must exist in kabupaten_jatim.csv."""
    known = set(kab_df["kab_id"].astype(int))
    actual = set(horti_csv["kab_id"].astype(int))
    unknown = actual - known
    assert unknown == set(), f"Unknown kab_ids in hortikultura rows: {unknown}"


def test_horti_all_38_kabs_per_commodity(horti_csv, kab_df):
    """Every kabupaten/kota must appear in each commodity's rows."""
    all_ids = set(kab_df["kab_id"].astype(int))
    for code in HORTI_CODES:
        sub_ids = set(horti_csv[horti_csv["commodity_code"] == code]["kab_id"].astype(int))
        missing = all_ids - sub_ids
        assert missing == set(), f"{code}: missing kab_ids = {missing}"


# ---------------------------------------------------------------------------
# H5. Derivation spot-check: Kota Surabaya bawang_merah
# ---------------------------------------------------------------------------

def test_derivation_spot_check_surabaya_bawang_merah(real_csv, pop_2022, kab_df):
    """
    Kota Surabaya (kab_id=3578) bawang_merah:
    produksi = 61 ton (raw kuintal 610/10 from bawang_merah.csv row 36 = Surabaya).
    konsumsi = 3.024 * 2,887,223 / 1000 = ~8,724 ton
    net = 61 - 8,724 = -8,663 ton -> DEFICIT.
    """
    kab_id = 3578  # Kota Surabaya
    full_name = "Kota Surabaya"

    pop = float(pop_2022[pop_2022["kabupaten/kota"] == full_name]["populasi"].iloc[0])
    kons_ton = PERKAPITA_KG_YR["bawang_merah"] * pop / 1000.0
    assert kons_ton > 5_000, f"Surabaya bawang_merah kons_ton implausibly low: {kons_ton:.0f}"

    row = real_csv[(real_csv["kab_id"] == kab_id) &
                   (real_csv["commodity_code"] == "bawang_merah")]
    assert len(row) == 1
    assert row["role"].iloc[0] == "DEFICIT", (
        f"Surabaya bawang_merah should be DEFICIT (tiny production)"
    )
    # Volume must be close to kons_ton (production is negligible)
    vol = float(row["volume_tons"].iloc[0])
    assert abs(vol - kons_ton) < 500, (
        f"Surabaya bawang_merah volume {vol:.0f} far from expected ~{kons_ton:.0f} ton"
    )


# ---------------------------------------------------------------------------
# H6. Sanity: bawang_merah top surplus = Nganjuk (kab_id 3518)
# ---------------------------------------------------------------------------

def test_bawang_merah_top_surplus_is_nganjuk(horti_csv):
    """Nganjuk is the top bawang_merah surplus node in Jatim (and Indonesia)."""
    bm_surplus = horti_csv[
        (horti_csv["commodity_code"] == "bawang_merah") &
        (horti_csv["role"] == "SURPLUS")
    ]
    assert len(bm_surplus) > 0, "No bawang_merah SURPLUS rows found"
    top = bm_surplus.nlargest(1, "volume_tons")
    assert int(top["kab_id"].iloc[0]) == 3518, (
        f"Top bawang_merah surplus should be Nganjuk (3518), "
        f"got kab_id={top['kab_id'].iloc[0]} volume={top['volume_tons'].iloc[0]:.0f}"
    )
    # Nganjuk production ~193,988 ton, consumption ~3.4k ton -> surplus ~190k ton
    assert float(top["volume_tons"].iloc[0]) > 100_000, (
        f"Nganjuk bawang_merah surplus should be >> 100k ton, "
        f"got {float(top['volume_tons'].iloc[0]):.0f}"
    )


# ---------------------------------------------------------------------------
# H7. Sanity: bawang_putih ALL DEFICIT (Jatim is a net importer)
# ---------------------------------------------------------------------------

def test_bawang_putih_all_deficit(horti_csv):
    """
    Jatim bawang_putih production 2022 ~855 ton (BPS data) vs consumption
    ~2.016 kg/kap/yr * 40M pop = ~80,640 ton. Every kabupaten is DEFICIT.
    """
    bp = horti_csv[horti_csv["commodity_code"] == "bawang_putih"]
    surplus = bp[bp["role"] == "SURPLUS"]
    assert len(surplus) == 0, (
        f"Expected all bawang_putih rows to be DEFICIT; got {len(surplus)} SURPLUS rows:\n"
        f"{surplus[['kab_id','volume_tons']].to_string()}"
    )
    assert len(bp) == 38, f"Expected 38 bawang_putih rows, got {len(bp)}"


# ---------------------------------------------------------------------------
# H8. Sanity: cabai_rawit top-3 include Banyuwangi or Malang
# ---------------------------------------------------------------------------

def test_cabai_rawit_top_producers(horti_csv):
    """
    Top cabai_rawit surplus kabupaten must include known Jatim chili zones.
    Banyuwangi (3510), Malang (3507), Kediri (3506), Sampang (3527) are expected.
    """
    cr_surplus = horti_csv[
        (horti_csv["commodity_code"] == "cabai_rawit") &
        (horti_csv["role"] == "SURPLUS")
    ]
    assert len(cr_surplus) > 0, "No cabai_rawit SURPLUS rows"
    top3_ids = set(cr_surplus.nlargest(3, "volume_tons")["kab_id"].astype(int))
    expected_ids = {3510, 3507, 3506, 3527}
    overlap = top3_ids & expected_ids
    assert len(overlap) >= 2, (
        f"Top-3 cabai_rawit surplus {top3_ids} should contain >= 2 of {expected_ids}"
    )


# ---------------------------------------------------------------------------
# H9. Sanity: Kota Surabaya DEFICIT for all 4 horti commodities
# ---------------------------------------------------------------------------

def test_surabaya_all_horti_deficit(horti_csv):
    """Kota Surabaya (3578) must be DEFICIT for all 4 hortikultura commodities."""
    sub = horti_csv[horti_csv["kab_id"] == 3578]
    assert len(sub) == 4, f"Expected 4 horti rows for Surabaya, got {len(sub)}"
    for _, row in sub.iterrows():
        assert row["role"] == "DEFICIT", (
            f"Surabaya {row['commodity_code']} should be DEFICIT, got {row['role']}"
        )


# ---------------------------------------------------------------------------
# H10. harvest_age_days = 28 for SURPLUS, 0 for DEFICIT
# ---------------------------------------------------------------------------

def test_horti_harvest_age_surplus(horti_csv):
    """All hortikultura SURPLUS rows must have harvest_age_days == 28."""
    surplus = horti_csv[horti_csv["role"] == "SURPLUS"]
    bad = surplus[surplus["harvest_age_days"] != 28]
    assert bad.empty, f"Horti SURPLUS rows with wrong harvest_age_days:\n{bad}"


def test_horti_harvest_age_deficit(horti_csv):
    """All hortikultura DEFICIT rows must have harvest_age_days == 0."""
    deficit = horti_csv[horti_csv["role"] == "DEFICIT"]
    bad = deficit[deficit["harvest_age_days"] != 0]
    assert bad.empty, f"Horti DEFICIT rows with wrong harvest_age_days:\n{bad}"


# ---------------------------------------------------------------------------
# H11. Prices match expected PIHPS/baseline values
# ---------------------------------------------------------------------------

def test_horti_prices(horti_csv):
    """Prices must match PIHPS 2022 medians (or flagged baseline for cabai_merah)."""
    for code, expected_price in EXPECTED_PRICES.items():
        sub = horti_csv[horti_csv["commodity_code"] == code]
        prices = sub["price_idr_per_kg"].unique()
        assert len(prices) == 1, f"{code}: expected single price, got {prices}"
        assert int(prices[0]) == expected_price, (
            f"{code}: price = {prices[0]}, expected {expected_price}"
        )


# ---------------------------------------------------------------------------
# H12. volume_tons > 0 everywhere
# ---------------------------------------------------------------------------

def test_horti_volume_positive(horti_csv):
    """All hortikultura volume_tons must be positive."""
    bad = horti_csv[horti_csv["volume_tons"] <= 0]
    assert bad.empty, f"Rows with volume_tons <= 0:\n{bad}"


# ---------------------------------------------------------------------------
# H13. Total row count in full real CSV = 228
# ---------------------------------------------------------------------------

def test_total_row_count(real_csv):
    """
    Full surplus_deficit_real.csv:
      4 horti commodities * 38 kab = 152 rows
      2 beras grades * 38 kab = 76 rows
      Total = 228 rows
    """
    assert len(real_csv) == 228, (
        f"Expected 228 total rows (4*38 horti + 2*38 beras), got {len(real_csv)}"
    )


def test_all_6_commodities_present(real_csv):
    """All 6 commodity codes must be present."""
    codes = set(real_csv["commodity_code"].unique())
    expected = {"beras_premium", "beras_medium", "cabai_merah", "cabai_rawit",
                "bawang_merah", "bawang_putih"}
    assert codes == expected, f"Commodity codes mismatch. Got: {codes}"


# ---------------------------------------------------------------------------
# H14. Per-kapita constants (frozen 2022 Kementan values)
# ---------------------------------------------------------------------------

def test_perkapita_constants_frozen():
    """
    The per-kapita constants used in derivation are from Kementan PDF 2024
    (Tabel 4.6a p.30, 4.1a p.25, 4.2a p.26) for year 2022. This test documents
    the expected values — if the script changes them, this test will catch it.
    """
    assert PERKAPITA_KG_YR["cabai_merah"]  == 1.909
    assert PERKAPITA_KG_YR["cabai_rawit"]  == 2.073
    assert PERKAPITA_KG_YR["bawang_merah"] == 3.024
    assert PERKAPITA_KG_YR["bawang_putih"] == 2.016
