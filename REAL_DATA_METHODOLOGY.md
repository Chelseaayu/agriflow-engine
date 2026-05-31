# Real Data Methodology — Surplus/Deficit Beras

## Status per commodity

| Commodity | Status | Source |
|---|---|---|
| `beras_premium` | REAL (derived) | BPS per-kabupaten produksi + konsumsi + populasi |
| `beras_medium` | REAL (derived, grade-split assumption — see below) | same |
| `cabai_merah`, `cabai_rawit` | PENDING — produksi per-kab not yet ingested | — |
| `bawang_merah` | PENDING | — |
| `jagung` | PENDING | — |
| All other commodities | PENDING | — |

The engine's existing `surplus_deficit.csv` retains synthetic placeholder values for all
non-beras commodities. `surplus_deficit_real.csv` contains **only beras** and is the
authoritative data file for beras routing decisions.

---

## Year used: 2024

All three input datasets (production, consumption, population) cover 2021–2025.
**2024** is selected as the reference year because the 2025 population file contains
values inflated by ~1000x (data entry error at source). See `sample_data/bps_real/PROVENANCE.md`.

The same year (2024) is used for all three inputs so the derivation is internally consistent:
consumption and population are matched to the same year as production.

---

## Data sources (all BPS-grade, per-kabupaten)

| Dataset | File | Source |
|---|---|---|
| Produksi beras (ton/tahun/kab) | `sample_data/bps_real/year_beras.csv` | BPS Jawa Timur — Produksi Beras Menurut Kab/Kota |
| Konsumsi per kapita (kg/minggu/kab) | `sample_data/bps_real/week_konsumsi_beras_perkapita.csv` | BPS Indonesia — Konsumsi Perkapita Seminggu, Kelompok Padi-Padian per Kab/Kota |
| Populasi (jiwa/tahun/kab) | `sample_data/bps_real/year_populasi_jatim.csv` | BPS Jawa Timur — Jumlah Penduduk per Kab/Kota |

**Key advantage over synthetic data**: consumption per kapita is real BPS survey data
at the kabupaten level — not a national average extrapolated to all districts. This means
urban-rural differences in rice consumption patterns (e.g., Kota Surabaya at 1.326 kg/week
vs Kabupaten Sampang at 1.891 kg/week) are captured in the derivation.

---

## Derivation formula

```
konsumsi_ton = avg_konsumsi_perkapita_kg_per_minggu × 52 × populasi / 1000
net_ton      = produksi_ton − konsumsi_ton
role         = "SURPLUS" if net_ton > 0 else "DEFICIT"
volume_tons  = abs(net_ton)
```

All arithmetic is applied per-kabupaten for year 2024. No interpolation, no imputation —
if a kabupaten were missing from any of the three datasets it would be reported and excluded.
(All 38 kabupaten/kota Jatim are present in all three datasets for 2024.)

---

## Grade split: ASSUMPTION

The engine uses two beras grades: `beras_premium` and `beras_medium`.

**Assumption**: 60 % of net volume → `beras_premium`; 40 % → `beras_medium`.

This split is a working assumption. A more rigorous approach would use BPS data on the
share of production by grade (e.g., IRRI grade or Bapanas mapping), or milling output
ratios by kabupaten. If that data becomes available, re-run the derivation with the
per-kabupaten premium/medium ratio.

---

## Prices: PIHPS median 2025

| Grade | Price (IDR/kg) | Source |
|---|---|---|
| `beras_premium` | 15,750 | Median of `beras_super_1` + `beras_super_2`, PIHPS daily panel 2025, across all 8 Kota IHK Jatim |
| `beras_medium` | 14,150 | Median of `beras_medium_1` + `beras_medium_2`, same panel |

PIHPS data vendored at `sample_data/price_history/super1_cleaned.csv`, `super2_cleaned.csv`,
`medium1_cleaned.csv`, `medium2_cleaned.csv`. See `sample_data/price_history/SOURCE.md` for
full attribution (PIHPS / Badan Pangan Nasional, via AgriFlow TimesFM team).

Note: prices are from 2025 PIHPS while volume is from 2024 BPS production. This is intentional —
prices represent the current market rate for matching-engine decisions, not the historical price
at the time of harvest.

---

## harvest_age_days

| Role | Value | Rationale |
|---|---|---|
| SURPLUS | 28 | Typical post-milling age when rice leaves origin kabupaten warehouse (conservative estimate based on milling-to-market lag in Jatim; range plausible: 20–35 days) |
| DEFICIT | 0 | Convention: deficit nodes are demand points, not supply points; age is irrelevant |

This is an assumption. If origin-specific milling-to-market data becomes available,
replace with per-kabupaten values.

---

## Name-to-kab_id mapping

Source data uses "Kabupaten X" / "Kota X" (BPS full names).
`kabupaten_jatim.csv` uses short names for kabupaten (e.g., "Lamongan") and "Kota X" for kota.

Mapping rule applied:
- "Kota X" in source → "Kota X" in reference → direct match
- "Kabupaten X" in source → "X" in reference → match after stripping "Kabupaten " prefix

All 38 kabupaten/kota matched without exceptions for year 2024.

---

## Sanity check results (2024)

Top surplus kabupaten (net_ton total beras):

| kab_id | Kabupaten | Produksi (ton) | Konsumsi (ton) | Net (ton) | Role |
|---|---|---|---|---|---|
| 3521 | Kab. Ngawi | 442,133 | 82,660 | +359,473 | SURPLUS |
| 3524 | Kab. Lamongan | 448,246 | 111,226 | +337,020 | SURPLUS |
| 3522 | Kab. Bojonegoro | 410,273 | 111,092 | +299,181 | SURPLUS |
| 3523 | Kab. Tuban | 302,030 | 95,311 | +206,719 | SURPLUS |
| 3519 | Kab. Madiun | 252,597 | 57,178 | +195,420 | SURPLUS |

Top deficit kabupaten:

| kab_id | Kabupaten | Produksi (ton) | Konsumsi (ton) | Net (ton) | Role |
|---|---|---|---|---|---|
| 3578 | Kota Surabaya | 4,239 | 201,478 | -197,239 | DEFICIT |
| 3573 | Kota Malang | 6,061 | 51,416 | -45,355 | DEFICIT |
| 3507 | Kab. Malang | 147,123 | 184,100 | -36,977 | DEFICIT |
| 3515 | Kab. Sidoarjo | 120,673 | 146,342 | -25,669 | DEFICIT |
| 3506 | Kab. Kediri | 100,513 | 123,552 | -23,039 | DEFICIT |

These match geographic expectations: Ngawi, Lamongan, Bojonegoro, Tuban are the paddy belt
of Jawa Timur; Surabaya, Malang, Sidoarjo are dense urban centres with minimal rice land.
