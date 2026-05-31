"""
derive_surplus_deficit_2022.py
==============================
Derives surplus_deficit_real.csv for ALL 6 commodities at reference year 2022.

Commodities produced:
  beras_premium, beras_medium   -- from BPS per-kab produksi + konsumsi + populasi (2022)
  cabai_merah                   -- cabai_besar + cabai_keriting, BPS Hortikultura 2022
  cabai_rawit                   -- BPS Hortikultura 2022
  bawang_merah                  -- BPS Hortikultura 2022
  bawang_putih                  -- BPS Hortikultura 2022

Units & conversions:
  Beras production  : ton/year (already ton in year_beras.csv)
  Hortikultural     : KUINTAL/year in source CSVs -> divide by 10 -> TON
  Beras consumption : kg/kapita/week -> x52 weeks x populasi / 1000 -> ton/year
  Hortikultura cons.: kg/kapita/year (national, from Kementan PDF) x populasi / 1000 -> ton/year

Per-capita consumption sources:
  Beras             : BPS Susenas per-kab (real), week_konsumsi_beras_perkapita.csv, 2022
  Cabai merah       : Kementan "Statistik Konsumsi Pangan 2024", Tabel 4.6a, p.30
                      Cabe merah (Chillies) 2022 = 1.909 kg/kapita/tahun  [NATIONAL PROXY]
  Cabai rawit       : same table, Cabe rawit (Cayenne pepper) 2022 = 2.073 kg/kapita/tahun [NATIONAL PROXY]
  Bawang merah      : same PDF, Tabel 4.1a, p.25
                      Bawang merah (Onion) 2022 = 3.024 kg/kapita/tahun  [NATIONAL PROXY]
  Bawang putih      : same PDF, Tabel 4.2a, p.26
                      Bawang putih (Garlic) 2022 = 2.016 kg/kapita/tahun  [NATIONAL PROXY]

Prices (2022 median from sample_data/price_history/ PIHPS data):
  beras_premium : median(super1, super2) 2022 = 11,500 IDR/kg
  beras_medium  : median(medium1, medium2) 2022 = 10,325 IDR/kg
  cabai_merah   : NOT in PIHPS dataset (cabai besar/keriting absent).
                  Using komoditas_constraints.csv baseline = 45,000 IDR/kg [FLAGGED]
  cabai_rawit   : cabe_rawit_cleaned.csv 2022 median = 41,000 IDR/kg [PIHPS real]
  bawang_merah  : bawang_merah_cleaned.csv 2022 median = 32,500 IDR/kg [PIHPS real]
  bawang_putih  : bawang_putih_cleaned.csv 2022 median = 20,750 IDR/kg [PIHPS real]

Excluded:
  daging_ayam, telur_ayam -- broiler hilang; telur petelur hanya 2 kab. PENDING.

Run:
  python sample_data/bps_real/derive_surplus_deficit_2022.py
"""

from __future__ import annotations

import pathlib
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = pathlib.Path(__file__).parent.parent.parent
BPS_DIR = ROOT / "sample_data" / "bps_real"
HORTI_DIR = pathlib.Path("D:/DOWNLOAD/Download 2026/baru-20260531T082645Z-3-001/baru")
PH_DIR = ROOT / "sample_data" / "price_history"
KAB_CSV = ROOT / "sample_data" / "kabupaten_jatim.csv"
OUT_CSV = ROOT / "sample_data" / "surplus_deficit_real.csv"

YEAR = 2022

# ---------------------------------------------------------------------------
# Per-capita consumption (NATIONAL PROXY — Kementan PDF, Tabel 4.6a/4.1a/4.2a)
# Source: Statistik Konsumsi Pangan 2024, Pusat Data Kementan, Desember 2024
# URL: https://satudata.pertanian.go.id/assets/docs/publikasi/Buku_Statistik_Konsumsi_2024.pdf
# ---------------------------------------------------------------------------
PERKAPITA_KG_PER_TAHUN = {
    "cabai_merah":  1.909,   # Tabel 4.6a p.30: Cabe merah / Chillies, 2022
    "cabai_rawit":  2.073,   # Tabel 4.6a p.30: Cabe rawit / Cayenne pepper, 2022
    "bawang_merah": 3.024,   # Tabel 4.1a p.25: Bawang merah / Onion, 2022
    "bawang_putih": 2.016,   # Tabel 4.2a p.26: Bawang putih / Garlic, 2022
}

# ---------------------------------------------------------------------------
# Prices IDR/kg (2022 median from PIHPS or flagged baseline)
# ---------------------------------------------------------------------------
PRICES = {
    "beras_premium": 11_500,  # median(super1=12000, super2=11000), PIHPS 2022
    "beras_medium":  10_325,  # median(medium1=10650, medium2=10000), PIHPS 2022
    "cabai_merah":   45_000,  # komoditas_constraints.csv baseline — NOT in PIHPS [FLAGGED]
    "cabai_rawit":   41_000,  # cabe_rawit_cleaned.csv 2022 median, PIHPS
    "bawang_merah":  32_500,  # bawang_merah_cleaned.csv 2022 median, PIHPS
    "bawang_putih":  20_750,  # bawang_putih_cleaned.csv 2022 median, PIHPS
}

# harvest_age_days by role
HARVEST_AGE = {"SURPLUS": 28, "DEFICIT": 0}

# Grade split for beras
PREMIUM_SPLIT = 0.60
MEDIUM_SPLIT  = 0.40

# ---------------------------------------------------------------------------
# Load kabupaten reference
# ---------------------------------------------------------------------------
def load_kab_map() -> dict[str, int]:
    """Returns {BPS-full-name -> kab_id} for all 38 Jatim kab/kota."""
    kab = pd.read_csv(KAB_CSV)
    mapping: dict[str, int] = {}
    for _, row in kab.iterrows():
        n = row["nama"]
        kid = int(row["kab_id"])
        if n.startswith("Kota "):
            mapping[n] = kid            # e.g. "Kota Surabaya" -> 3578
        else:
            mapping["Kabupaten " + n] = kid  # e.g. "Kabupaten Lamongan" -> 3524
    return mapping


def load_kab_ids_ordered() -> list[int]:
    """
    Returns list of 38 kab_ids in BPS hortikultura row order:
    rows 0-28 = Kabupaten (by BPS sequential code 3501-3529),
    rows 29-37 = Kota (3571-3579).
    """
    kab = pd.read_csv(KAB_CSV)
    # Kabupaten (non-kota) sorted by kab_id ascending
    non_kota = kab[~kab["nama"].str.startswith("Kota ")].sort_values("kab_id")
    # Kota sorted by kab_id ascending: 3571 Kediri, 3572 Blitar, 3573 Malang,
    #                                  3574 Probolinggo, 3575 Pasuruan, 3576 Mojokerto,
    #                                  3577 Madiun, 3578 Surabaya, 3579 Batu
    kota = kab[kab["nama"].str.startswith("Kota ")].sort_values("kab_id")
    return list(non_kota["kab_id"].astype(int)) + list(kota["kab_id"].astype(int))


# ---------------------------------------------------------------------------
# Load hortikultura CSV (wide format, BPS, kuintal)
# Returns Series indexed by position 0-37, values in TON (after /10)
# Excludes Total row; treats NaN as 0.
# ---------------------------------------------------------------------------
def load_horti_csv(filename: str) -> pd.Series:
    df = pd.read_csv(HORTI_DIR / filename, encoding="utf-8-sig")
    # Row 38 (or last row) is "Total" — drop it
    df = df[df["Kabupaten"] != "Total"].copy()
    assert len(df) == 38, (
        f"{filename}: expected 38 data rows after excluding Total, got {len(df)}"
    )
    prod_kuintal = df["Produksi_2022"].fillna(0.0).reset_index(drop=True)
    prod_ton = prod_kuintal / 10.0  # KUINTAL -> TON
    return prod_ton


# ---------------------------------------------------------------------------
# Derive beras surplus/deficit rows (2022)
# ---------------------------------------------------------------------------
def derive_beras(kab_map: dict[str, int], kab_ids_38: list[int]) -> list[dict]:
    prod_df = pd.read_csv(BPS_DIR / "year_beras.csv")
    kons_df = pd.read_csv(BPS_DIR / "week_konsumsi_beras_perkapita.csv")
    pop_df  = pd.read_csv(BPS_DIR / "year_populasi_jatim.csv")

    prod22 = prod_df[prod_df["tahun"] == YEAR].copy()
    kons22 = kons_df[kons_df["tahun"] == YEAR].copy()
    pop22  = pop_df[pop_df["tahun"] == YEAR].copy()

    assert len(prod22) == 38, f"Beras produksi 2022: expected 38 rows, got {len(prod22)}"
    assert len(kons22) == 38, f"Beras konsumsi 2022: expected 38 rows, got {len(kons22)}"
    assert len(pop22)  == 38, f"Populasi 2022: expected 38 rows, got {len(pop22)}"

    rows: list[dict] = []

    for _, prod_row in prod22.iterrows():
        kab_name = prod_row["kabupaten"]          # e.g. "Kabupaten Lamongan"
        kab_id   = kab_map[kab_name]
        produksi = float(prod_row["produksi"])    # ton

        kons_row = kons22[kons22["kabupaten/kota"] == kab_name]
        pop_row  = pop22[pop22["kabupaten/kota"]   == kab_name]
        assert len(kons_row) == 1, f"Missing konsumsi for {kab_name}"
        assert len(pop_row)  == 1, f"Missing populasi for {kab_name}"

        kg_per_week = float(kons_row["avg_konsumsi_perkapita_kg"].iloc[0])
        populasi    = float(pop_row["populasi"].iloc[0])
        konsumsi_ton = kg_per_week * 52.0 * populasi / 1000.0
        net_ton      = produksi - konsumsi_ton
        role         = "SURPLUS" if net_ton > 0 else "DEFICIT"
        vol          = abs(net_ton)

        for code, split in [("beras_premium", PREMIUM_SPLIT), ("beras_medium", MEDIUM_SPLIT)]:
            rows.append({
                "kab_id":           kab_id,
                "commodity_code":   code,
                "role":             role,
                "volume_tons":      round(vol * split, 2),
                "price_idr_per_kg": PRICES[code],
                "harvest_age_days": HARVEST_AGE[role],
            })

    return rows


# ---------------------------------------------------------------------------
# Derive hortikultura surplus/deficit rows (2022)
# ---------------------------------------------------------------------------
def derive_horti(kab_ids_38: list[int], pop22_series: pd.Series) -> list[dict]:
    """
    kab_ids_38  : list of 38 kab_ids in BPS row order
    pop22_series: pd.Series of 38 populasi values in same row order
    """
    # Load production files (ton after conversion)
    cabai_besar   = load_horti_csv("cabai_besar.csv")
    cabai_keriting = load_horti_csv("cabai_keriting.csv")
    cabai_rawit   = load_horti_csv("cabai_rawit.csv")
    bawang_merah  = load_horti_csv("bawang_merah.csv")
    bawang_putih  = load_horti_csv("bawang_putih.csv")

    # cabai_merah = besar + keriting
    cabai_merah_prod = cabai_besar + cabai_keriting

    commodities = {
        "cabai_merah":  cabai_merah_prod,
        "cabai_rawit":  cabai_rawit,
        "bawang_merah": bawang_merah,
        "bawang_putih": bawang_putih,
    }

    rows: list[dict] = []
    for code, prod_series in commodities.items():
        per_kapita = PERKAPITA_KG_PER_TAHUN[code]  # kg/kapita/tahun (national)
        price      = PRICES[code]

        for i in range(38):
            kab_id      = kab_ids_38[i]
            produksi    = float(prod_series.iloc[i])     # ton
            populasi    = float(pop22_series.iloc[i])    # jiwa
            konsumsi_ton = per_kapita * populasi / 1000.0
            net_ton      = produksi - konsumsi_ton
            role         = "SURPLUS" if net_ton > 0 else "DEFICIT"
            vol          = abs(net_ton)

            rows.append({
                "kab_id":           kab_id,
                "commodity_code":   code,
                "role":             role,
                "volume_tons":      round(vol, 2),
                "price_idr_per_kg": price,
                "harvest_age_days": HARVEST_AGE[role],
            })

    return rows


# ---------------------------------------------------------------------------
# Build population series in BPS row order (same as kab_ids_38)
# ---------------------------------------------------------------------------
def build_pop22_series(kab_ids_38: list[int]) -> pd.Series:
    """
    Returns a pd.Series of 2022 population values in kab_ids_38 order.
    Uses year_populasi_jatim.csv (same file as beras derivation).
    """
    pop_df = pd.read_csv(BPS_DIR / "year_populasi_jatim.csv")
    pop22  = pop_df[pop_df["tahun"] == YEAR].copy()

    # Build id->pop dict using the same kab_map approach
    kab = pd.read_csv(KAB_CSV)
    name_to_id: dict[str, int] = {}
    for _, row in kab.iterrows():
        n = row["nama"]
        kid = int(row["kab_id"])
        if n.startswith("Kota "):
            name_to_id[n] = kid
        else:
            name_to_id["Kabupaten " + n] = kid

    id_to_pop = {}
    for _, r in pop22.iterrows():
        full_name = r["kabupaten/kota"]
        kid = name_to_id.get(full_name)
        if kid is not None:
            id_to_pop[kid] = float(r["populasi"])

    assert len(id_to_pop) == 38, f"Expected 38 pop entries, got {len(id_to_pop)}"

    values = [id_to_pop[kid] for kid in kab_ids_38]
    return pd.Series(values, name="populasi")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print(f"Deriving surplus_deficit_real.csv @ year {YEAR} ...")

    kab_map     = load_kab_map()
    kab_ids_38  = load_kab_ids_ordered()
    pop22_series = build_pop22_series(kab_ids_38)

    beras_rows = derive_beras(kab_map, kab_ids_38)
    horti_rows = derive_horti(kab_ids_38, pop22_series)

    all_rows = beras_rows + horti_rows
    df = pd.DataFrame(all_rows, columns=[
        "kab_id", "commodity_code", "role",
        "volume_tons", "price_idr_per_kg", "harvest_age_days",
    ])

    # Sort: surplus first (descending volume), then deficit, grouped by commodity
    df = df.sort_values(
        ["commodity_code", "role", "volume_tons"],
        ascending=[True, True, False],  # role: DEFICIT < SURPLUS alphabetically; flip
    )
    # Re-sort: SURPLUS first within each commodity
    df["_role_order"] = df["role"].map({"SURPLUS": 0, "DEFICIT": 1})
    df = df.sort_values(["commodity_code", "_role_order", "volume_tons"],
                        ascending=[True, True, False])
    df = df.drop(columns=["_role_order"]).reset_index(drop=True)

    df.to_csv(OUT_CSV, index=False)
    print(f"Written {len(df)} rows to {OUT_CSV}")

    # Sanity report
    print("\n--- Sanity check: top-3 producers per commodity (production ton) ---")
    # Recompute production for display
    for code in ["cabai_merah","cabai_rawit","bawang_merah","bawang_putih"]:
        sub = df[df["commodity_code"] == code].copy()
        kab_ref = pd.read_csv(KAB_CSV)
        id_to_name = dict(zip(kab_ref["kab_id"].astype(int), kab_ref["nama"]))
        surplus = sub[sub["role"] == "SURPLUS"].nlargest(3, "volume_tons")
        print(f"\n{code}:")
        for _, r in surplus.iterrows():
            print(f"  kab_id={r['kab_id']} ({id_to_name.get(r['kab_id'],'?')}) "
                  f"surplus={r['volume_tons']:,.0f} ton")

    for code in ["beras_premium","beras_medium"]:
        sub = df[df["commodity_code"] == code]
        kab_ref = pd.read_csv(KAB_CSV)
        id_to_name = dict(zip(kab_ref["kab_id"].astype(int), kab_ref["nama"]))
        surplus = sub[sub["role"] == "SURPLUS"].nlargest(3, "volume_tons")
        print(f"\n{code}:")
        for _, r in surplus.iterrows():
            print(f"  kab_id={r['kab_id']} ({id_to_name.get(r['kab_id'],'?')}) "
                  f"surplus={r['volume_tons']:,.0f} ton")

    print("\n--- Commodity row counts ---")
    print(df.groupby(["commodity_code","role"]).size().to_string())
    print(f"\nTotal rows: {len(df)}")


if __name__ == "__main__":
    main()
