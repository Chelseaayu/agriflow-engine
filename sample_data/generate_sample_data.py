"""
Generator sample data CSV untuk 38 kabupaten/kota Jawa Timur.

Data sources:
    - Kode wilayah & nama: Permendagri 137/2017
    - IPM 2024: BPS Jatim (https://jatim.bps.go.id/)
                ringkasan: jatimtimes.com & manadopost berdasarkan Berita Resmi Statistik
    - Koordinat: Approximate kabupaten/kota center (lat/lon)
    - Population 2024: BPS Jawa Timur Dalam Angka 2025
    - 8 Kota IHK: PIHPS Bank Indonesia (https://www.bi.go.id/hargapangan/)

Catatan: Beberapa IPM di proposal v7/v8 (e.g., Sampang 61.6) berasal dari
data tahun lebih lawas. v9 pakai IPM 2024 BPS. Tim wajib refresh tahunan
saat BPS publish data baru (biasanya November-Desember).
"""

import csv
import os
import sys

# Force UTF-8 stdout di Windows (default cp1252 crash di "✓").
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))


# =============================================================================
# 38 Kabupaten/Kota Jawa Timur — Master Data
# =============================================================================
# Kolom: kab_id, nama, latitude, longitude, ipm_2024, population_2024, tier
# Tier: TIER_1_HIGH untuk 8 kota IHK, TIER_2_MEDIUM untuk sisanya
# IPM mengikuti sumber BPS 2024 (atau estimasi konservatif jika tidak tersedia)

KABUPATEN_DATA = [
    # ===== TIER 1 — 8 Kota IHK Jatim =====
    ("3578", "Kota Surabaya",      -7.2575, 112.7521, 84.69, 2949496, "TIER_1_HIGH"),
    ("3573", "Kota Malang",        -7.9666, 112.6326, 84.68,  844614, "TIER_1_HIGH"),
    ("3571", "Kota Kediri",        -7.8166, 112.0114, 81.48,  287609, "TIER_1_HIGH"),
    ("3577", "Kota Madiun",        -7.6298, 111.5300, 81.67,  178540, "TIER_1_HIGH"),
    ("3574", "Kota Probolinggo",   -7.7543, 113.2159, 79.20,  239649, "TIER_1_HIGH"),
    ("3510", "Banyuwangi",         -8.2192, 114.3691, 73.45, 1719287, "TIER_1_HIGH"),
    ("3529", "Sumenep",            -7.0067, 113.8525, 68.79, 1144719, "TIER_1_HIGH"),
    ("3509", "Jember",             -8.1727, 113.7000, 71.86, 2606656, "TIER_1_HIGH"),

    # ===== TIER 2 — 30 Kabupaten Non-IHK =====
    ("3501", "Pacitan",            -8.1985, 111.1014, 71.40,  592786, "TIER_2_MEDIUM"),
    ("3502", "Ponorogo",           -7.8674, 111.4625, 73.20,  956000, "TIER_2_MEDIUM"),
    ("3503", "Trenggalek",         -8.0497, 111.7100, 73.85,  733700, "TIER_2_MEDIUM"),
    ("3504", "Tulungagung",        -8.0658, 111.9028, 75.30, 1077500, "TIER_2_MEDIUM"),
    ("3505", "Blitar",             -8.0950, 112.1658, 73.85, 1213000, "TIER_2_MEDIUM"),
    ("3506", "Kediri",             -7.7960, 112.1700, 74.50, 1626100, "TIER_2_MEDIUM"),
    ("3507", "Malang",             -8.1706, 112.5290, 75.50, 2716000, "TIER_2_MEDIUM"),
    ("3508", "Lumajang",           -8.1336, 113.2245, 70.10, 1129500, "TIER_2_MEDIUM"),
    ("3511", "Bondowoso",          -7.9134, 113.8217, 69.62,  790180, "TIER_2_MEDIUM"),
    ("3512", "Situbondo",          -7.7068, 114.0093, 71.20,  690600, "TIER_2_MEDIUM"),
    ("3513", "Probolinggo",        -7.8742, 113.4675, 69.40, 1208400, "TIER_2_MEDIUM"),
    ("3514", "Pasuruan",           -7.7460, 112.9237, 71.30, 1683700, "TIER_2_MEDIUM"),
    ("3515", "Sidoarjo",           -7.4549, 112.7178, 80.13, 2185300, "TIER_2_MEDIUM"),
    ("3516", "Mojokerto",          -7.4720, 112.4390, 76.50, 1175000, "TIER_2_MEDIUM"),
    ("3517", "Jombang",            -7.5460, 112.2308, 75.10, 1357300, "TIER_2_MEDIUM"),
    ("3518", "Nganjuk",            -7.6050, 111.9023, 75.20, 1075800, "TIER_2_MEDIUM"),
    ("3519", "Madiun",             -7.5570, 111.6890, 73.55,  743200, "TIER_2_MEDIUM"),
    ("3520", "Magetan",            -7.6515, 111.3287, 75.80,  679000, "TIER_2_MEDIUM"),
    ("3521", "Ngawi",              -7.4080, 111.4458, 74.40,  889600, "TIER_2_MEDIUM"),
    ("3522", "Bojonegoro",         -7.1500, 111.8800, 73.10, 1357000, "TIER_2_MEDIUM"),
    ("3523", "Tuban",              -6.8970, 111.9750, 74.30, 1218000, "TIER_2_MEDIUM"),
    ("3524", "Lamongan",           -7.1155, 112.4170, 75.60, 1378200, "TIER_2_MEDIUM"),
    ("3525", "Gresik",             -7.1568, 112.6510, 77.61, 1330000, "TIER_2_MEDIUM"),
    ("3526", "Bangkalan",          -7.0317, 112.7491, 67.70, 1062200, "TIER_2_MEDIUM"),
    ("3527", "Sampang",            -7.1924, 113.2473, 66.72,  984000, "TIER_2_MEDIUM"),
    ("3528", "Pamekasan",          -7.1565, 113.4785, 70.43,  892800, "TIER_2_MEDIUM"),
    ("3572", "Kota Blitar",        -8.0980, 112.1681, 80.20,  148800, "TIER_2_MEDIUM"),
    ("3575", "Kota Pasuruan",      -7.6469, 112.9070, 79.50,  211800, "TIER_2_MEDIUM"),
    ("3576", "Kota Mojokerto",     -7.4719, 112.4341, 80.85,  146100, "TIER_2_MEDIUM"),
    ("3579", "Kota Batu",          -7.8740, 112.5240, 78.30,  213700, "TIER_2_MEDIUM"),
]

assert len(KABUPATEN_DATA) == 38, f"Expected 38 kab, got {len(KABUPATEN_DATA)}"


# =============================================================================
# 19 Komoditas Bapanas + spec konstrain
# =============================================================================
# Kolom: code, nama, max_distance_km, min_viable_tons, max_fresh_age_days,
#        baseline_price_idr_per_kg

KOMODITAS_DATA = [
    ("cabai_merah",    "Cabai Merah Besar",            200, 1.0,   5,  45000),
    ("cabai_rawit",    "Cabai Rawit Merah",            200, 1.0,   5,  60000),
    ("bawang_merah",   "Bawang Merah",                 400, 2.0,  30,  35000),
    ("bawang_putih",   "Bawang Putih (Bonggol)",       600, 2.0,  60,  40000),
    ("tomat",          "Tomat Sayur",                  150, 1.0,   7,  12000),
    ("kentang",        "Kentang",                      400, 2.0,  21,  14000),
    ("kol",            "Kol/Kubis",                    300, 2.0,  14,   8000),
    ("wortel",         "Wortel",                       300, 2.0,  14,  11000),
    ("beras_premium",  "Beras Premium",                800, 5.0, 180,  15500),
    ("beras_medium",   "Beras Medium",                 800, 5.0, 180,  13000),
    ("jagung",         "Jagung Pipilan Kering",        600, 5.0, 120,   6000),
    ("kedelai",        "Kedelai Lokal",                600, 3.0, 120,  11000),
    ("telur_ayam",     "Telur Ayam Ras",               300, 1.0,  21,  29000),
    ("daging_ayam",    "Daging Ayam Ras",              200, 0.5,   3,  37000),
    ("daging_sapi",    "Daging Sapi Murni",            200, 0.5,   3, 138000),
    ("gula_pasir",     "Gula Pasir Lokal",             600, 3.0, 365,  18000),
    ("minyak_goreng",  "Minyak Goreng Curah",          600, 3.0, 180,  16500),
    ("ikan_segar",     "Ikan Segar (Bandeng/Tongkol)", 150, 0.5,   2,  35000),
    ("tepung_terigu",  "Tepung Terigu",                600, 3.0, 180,  13000),
]

assert len(KOMODITAS_DATA) == 19, f"Expected 19 komoditas, got {len(KOMODITAS_DATA)}"


# =============================================================================
# Sample Surplus / Deficit per kabupaten (realistic seasonal pattern)
# =============================================================================
# Pattern berbasis observasi pasar Jatim April 2026:
#   - Kediri, Tulungagung, Blitar: sentra cabai (surplus)
#   - Probolinggo, Pasuruan, Lumajang: sentra bawang (surplus)
#   - Madura (Bangkalan/Sampang/Pamekasan/Sumenep): sentra bawang (surplus)
#   - Banyuwangi, Jember: sentra hortikultura mixed
#   - Tuban, Lamongan, Bojonegoro, Ngawi: sentra padi (surplus beras)
#   - Surabaya, Sidoarjo, Gresik, Malang Kota: pasar besar (deficit)
#   - Pacitan, Trenggalek: relatif kecil, mostly subsisten
#
# Format: (kab_id, commodity_code, role, volume_tons, price_idr_per_kg, harvest_age_days)
# role: "SURPLUS" atau "DEFICIT"

SURPLUS_DEFICIT_DATA = [
    # ===== Cabai merah =====
    # Sentra cabai Jatim
    ("3506", "cabai_merah", "SURPLUS",  85.0, 38000, 2),  # Kab Kediri
    ("3504", "cabai_merah", "SURPLUS",  60.0, 39000, 1),  # Tulungagung
    ("3505", "cabai_merah", "SURPLUS",  45.0, 40000, 2),  # Kab Blitar
    ("3503", "cabai_merah", "SURPLUS",  20.0, 41000, 1),  # Trenggalek
    ("3508", "cabai_merah", "SURPLUS",  15.0, 42000, 2),  # Lumajang
    # Pasar besar (deficit)
    ("3578", "cabai_merah", "DEFICIT",  80.0, 65000, 0),  # Surabaya
    ("3515", "cabai_merah", "DEFICIT",  35.0, 62000, 0),  # Sidoarjo
    ("3525", "cabai_merah", "DEFICIT",  30.0, 60000, 0),  # Gresik
    ("3573", "cabai_merah", "DEFICIT",  25.0, 58000, 0),  # Kota Malang
    # Skenario A3: Sampang surplus mini, demand jauh
    ("3527", "cabai_merah", "SURPLUS",   2.0, 42000, 3),  # Sampang (mini)

    # ===== Cabai rawit =====
    ("3506", "cabai_rawit", "SURPLUS",  40.0, 52000, 2),  # Kab Kediri
    ("3504", "cabai_rawit", "SURPLUS",  30.0, 53000, 1),  # Tulungagung
    ("3508", "cabai_rawit", "SURPLUS",  25.0, 54000, 2),  # Lumajang
    ("3578", "cabai_rawit", "DEFICIT",  60.0, 75000, 0),  # Surabaya
    ("3573", "cabai_rawit", "DEFICIT",  20.0, 72000, 0),  # Kota Malang

    # ===== Bawang merah =====
    # Sentra Probolinggo / Pasuruan / Madura
    ("3513", "bawang_merah", "SURPLUS", 120.0, 28000, 5),  # Kab Probolinggo
    ("3514", "bawang_merah", "SURPLUS",  80.0, 29000, 6),  # Kab Pasuruan
    ("3526", "bawang_merah", "SURPLUS",  40.0, 30000, 4),  # Bangkalan (cluster Madura)
    ("3527", "bawang_merah", "SURPLUS",  35.0, 30000, 3),  # Sampang   (cluster Madura)
    ("3528", "bawang_merah", "SURPLUS",  45.0, 29500, 5),  # Pamekasan (cluster Madura)
    ("3529", "bawang_merah", "SURPLUS",  60.0, 29000, 6),  # Sumenep   (cluster Madura)
    ("3578", "bawang_merah", "DEFICIT", 150.0, 42000, 0),  # Surabaya
    ("3515", "bawang_merah", "DEFICIT",  60.0, 40000, 0),  # Sidoarjo
    ("3573", "bawang_merah", "DEFICIT",  35.0, 41000, 0),  # Kota Malang
    ("3525", "bawang_merah", "DEFICIT",  40.0, 39000, 0),  # Gresik

    # ===== Tomat =====
    ("3507", "tomat", "SURPLUS", 50.0, 8000, 2),   # Kab Malang (Pujon-Batu area)
    ("3579", "tomat", "SURPLUS", 30.0, 8500, 1),   # Kota Batu
    ("3505", "tomat", "SURPLUS", 25.0, 9000, 2),   # Kab Blitar
    ("3578", "tomat", "DEFICIT", 60.0, 14000, 0),  # Surabaya
    ("3525", "tomat", "DEFICIT", 25.0, 13500, 0),  # Gresik

    # ===== Kentang =====
    ("3507", "kentang", "SURPLUS", 35.0, 10000, 5),  # Kab Malang
    ("3579", "kentang", "SURPLUS", 25.0, 10500, 4),  # Kota Batu
    ("3578", "kentang", "DEFICIT", 45.0, 16000, 0),  # Surabaya
    ("3573", "kentang", "DEFICIT", 15.0, 15000, 0),  # Kota Malang

    # ===== Kol =====
    ("3579", "kol",    "SURPLUS", 40.0, 5500, 3),   # Kota Batu
    ("3507", "kol",    "SURPLUS", 30.0, 5800, 4),   # Kab Malang
    ("3578", "kol",    "DEFICIT", 50.0, 9500, 0),   # Surabaya

    # ===== Wortel =====
    ("3579", "wortel", "SURPLUS", 28.0, 8000, 3),   # Kota Batu
    ("3507", "wortel", "SURPLUS", 22.0, 8200, 4),   # Kab Malang
    ("3578", "wortel", "DEFICIT", 35.0, 12500, 0),  # Surabaya

    # ===== Beras premium =====
    ("3523", "beras_premium", "SURPLUS", 850.0, 14500, 30),  # Tuban
    ("3524", "beras_premium", "SURPLUS", 700.0, 14600, 25),  # Lamongan
    ("3522", "beras_premium", "SURPLUS", 650.0, 14400, 35),  # Bojonegoro
    ("3521", "beras_premium", "SURPLUS", 500.0, 14300, 28),  # Ngawi
    ("3578", "beras_premium", "DEFICIT", 800.0, 17000,  0),  # Surabaya
    ("3525", "beras_premium", "DEFICIT", 350.0, 16800,  0),  # Gresik
    ("3515", "beras_premium", "DEFICIT", 400.0, 16500,  0),  # Sidoarjo

    # ===== Beras medium (Bulog priority candidate) =====
    ("3519", "beras_medium",  "SURPLUS", 1200.0, 12500, 20), # Madiun (Bulog priority)
    ("3520", "beras_medium",  "SURPLUS",  800.0, 12600, 22), # Magetan
    ("3521", "beras_medium",  "SURPLUS",  900.0, 12400, 25), # Ngawi
    ("3578", "beras_medium",  "DEFICIT", 1000.0, 14500,  0), # Surabaya

    # ===== Jagung =====
    ("3522", "jagung", "SURPLUS", 800.0, 5500, 15),  # Bojonegoro
    ("3521", "jagung", "SURPLUS", 600.0, 5400, 18),  # Ngawi
    ("3502", "jagung", "SURPLUS", 400.0, 5600, 20),  # Ponorogo
    ("3578", "jagung", "DEFICIT", 700.0, 7200,  0),  # Surabaya (industri pakan)
    ("3525", "jagung", "DEFICIT", 400.0, 7000,  0),  # Gresik

    # ===== Telur ayam =====
    ("3505", "telur_ayam", "SURPLUS", 80.0, 26000, 1),   # Kab Blitar (sentra)
    ("3506", "telur_ayam", "SURPLUS", 50.0, 26500, 2),   # Kab Kediri
    ("3578", "telur_ayam", "DEFICIT", 90.0, 32000, 0),   # Surabaya
    ("3573", "telur_ayam", "DEFICIT", 25.0, 30500, 0),   # Kota Malang

    # ===== Daging ayam =====
    ("3505", "daging_ayam", "SURPLUS", 30.0, 32000, 1),  # Kab Blitar
    ("3506", "daging_ayam", "SURPLUS", 20.0, 33000, 1),  # Kab Kediri
    ("3578", "daging_ayam", "DEFICIT", 40.0, 40000, 0),  # Surabaya

    # ===== Ikan segar =====
    ("3525", "ikan_segar", "SURPLUS", 25.0, 28000, 1),   # Gresik (pesisir)
    ("3525", "ikan_segar", "SURPLUS", 20.0, 30000, 1),   # Lamongan
    ("3573", "ikan_segar", "DEFICIT", 15.0, 38000, 0),   # Kota Malang
    ("3577", "ikan_segar", "DEFICIT",  8.0, 36000, 0),   # Kota Madiun (pegunungan)

    # ===== Deficits di kab IPM rendah (demonstrate equity multiplier v9) =====
    # Threshold v9: <68→1.30 | <72→1.15 | <78→1.05 | ≥78→1.00 (kalibrasi BPS 2024)
    # Madura tidak produksi padi → impor beras
    ("3527", "beras_premium", "DEFICIT", 200.0, 16500, 0),   # Sampang IPM 66.72 → +30%
    ("3526", "beras_premium", "DEFICIT", 250.0, 16400, 0),   # Bangkalan IPM 67.70 → +30%
    ("3528", "beras_medium",  "DEFICIT", 180.0, 14000, 0),   # Pamekasan IPM 70.43 → +15%
    # Bondowoso pegunungan → defisit ikan & sayur
    ("3511", "ikan_segar", "DEFICIT",  6.0, 38000, 0),   # Bondowoso IPM 69.62 → +15%
    ("3511", "tomat",      "DEFICIT", 12.0, 13500, 0),   # Bondowoso → +15%
    # Sumenep (Tier 1 IHK tapi IPM rendah → equity boost +15%)
    ("3529", "cabai_merah", "DEFICIT", 8.0, 60000, 0),   # Sumenep IPM 68.79 → +15%
]


# =============================================================================
# Weather forecast sample untuk sebagian rute (BMKG-style)
# =============================================================================
# Skenario D1 Banjir Rute: hujan deras di rute Kediri → Surabaya (April monsoon)
# Format: origin_kab_id, dest_kab_id, max_rain_mm, transit_window_days, source

WEATHER_DATA = [
    # Hujan deras di rute Kediri-Surabaya (skenario D1)
    ("3506", "3578", 75.0, 1, "BMKG"),   # Kab Kediri → Surabaya
    ("3571", "3578", 70.0, 1, "BMKG"),   # Kota Kediri → Surabaya
    # Rute Madura cerah
    ("3527", "3578", 5.0, 1, "BMKG"),    # Sampang → Surabaya
    ("3526", "3578", 8.0, 1, "BMKG"),    # Bangkalan → Surabaya
    # Rute pegunungan moderate
    ("3507", "3578", 25.0, 1, "BMKG"),   # Kab Malang → Surabaya
    ("3579", "3578", 30.0, 1, "BMKG"),   # Kota Batu → Surabaya
    # Rute Probolinggo cerah
    ("3513", "3578", 10.0, 1, "BMKG"),   # Probolinggo → Surabaya
    ("3514", "3578", 12.0, 1, "BMKG"),   # Pasuruan → Surabaya
    # Rute Lumbung Padi (default cerah)
    ("3523", "3578",  8.0, 1, "BMKG"),   # Tuban → Surabaya
    ("3524", "3578",  6.0, 1, "BMKG"),   # Lamongan → Surabaya
]


# =============================================================================
# Historical price stats untuk anomaly detection (skenario D3)
# =============================================================================
# 30-day rolling median + std per komoditas. Kalau current price > 3σ → outlier.
# Format: commodity_code, median_idr_per_kg, std_idr_per_kg

HISTORICAL_PRICE_STATS = [
    ("cabai_merah",    45000, 8000),
    ("cabai_rawit",    60000, 12000),
    ("bawang_merah",   35000, 5000),
    ("bawang_putih",   40000, 6000),
    ("tomat",          12000, 2500),
    ("kentang",        14000, 2000),
    ("kol",             8000, 1500),
    ("wortel",         11000, 2000),
    ("beras_premium",  15500, 1500),
    ("beras_medium",   13000, 1200),
    ("jagung",          6000,  800),
    ("kedelai",        11000, 1500),
    ("telur_ayam",     29000, 3500),
    ("daging_ayam",    37000, 4500),
    ("daging_sapi",   138000,12000),
    ("gula_pasir",     18000, 1500),
    ("minyak_goreng",  16500, 2000),
    ("ikan_segar",     35000, 5000),
    ("tepung_terigu",  13000, 1200),
]


# =============================================================================
# WRITE CSV FILES
# =============================================================================

def write_csv(filename, header, rows):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"  ✓ {filename} ({len(rows)} rows)")


def main():
    print("Generating AgriFlow sample data CSVs...")

    write_csv(
        "kabupaten_jatim.csv",
        ["kab_id", "nama", "latitude", "longitude", "ipm_2024",
         "population_2024", "tier"],
        KABUPATEN_DATA,
    )
    write_csv(
        "komoditas_constraints.csv",
        ["code", "nama", "max_distance_km", "min_viable_tons",
         "max_fresh_age_days", "baseline_price_idr_per_kg"],
        KOMODITAS_DATA,
    )
    write_csv(
        "surplus_deficit.csv",
        ["kab_id", "commodity_code", "role", "volume_tons",
         "price_idr_per_kg", "harvest_age_days"],
        SURPLUS_DEFICIT_DATA,
    )
    write_csv(
        "weather_forecast.csv",
        ["origin_kab_id", "dest_kab_id", "max_rain_mm",
         "transit_window_days", "source"],
        WEATHER_DATA,
    )
    write_csv(
        "historical_price_stats.csv",
        ["commodity_code", "median_idr_per_kg", "std_idr_per_kg"],
        HISTORICAL_PRICE_STATS,
    )

    # Summary
    n_surplus = sum(1 for r in SURPLUS_DEFICIT_DATA if r[2] == "SURPLUS")
    n_deficit = sum(1 for r in SURPLUS_DEFICIT_DATA if r[2] == "DEFICIT")
    print(f"\nSummary:")
    print(f"  - {len(KABUPATEN_DATA)} kabupaten/kota")
    print(f"    - Tier 1 (HIGH):  {sum(1 for r in KABUPATEN_DATA if r[6] == 'TIER_1_HIGH')}")
    print(f"    - Tier 2 (MEDIUM): {sum(1 for r in KABUPATEN_DATA if r[6] == 'TIER_2_MEDIUM')}")
    print(f"  - {len(KOMODITAS_DATA)} komoditas")
    print(f"  - {n_surplus} surplus + {n_deficit} deficit nodes "
          f"({len(SURPLUS_DEFICIT_DATA)} total)")
    print(f"  - {len(WEATHER_DATA)} weather forecast entries")
    print(f"  - {len(HISTORICAL_PRICE_STATS)} historical price stats")


if __name__ == "__main__":
    main()
