# Price History Data — Source & Attribution

## Origin

These 9 CSV files are vendored from the AgriFlow team repository:

- **Repo**: `github.com/Chelseaayu/timesfm-prediction-system-agriflow`
- **Branch**: `main`
- **Remote path**: `data/*_cleaned.csv`
- **Date retrieved**: 2026-05-30

Original data source: **PIHPS (Panel Harga Pangan Strategis)** — Badan Pangan Nasional (Bapanas).
Price observations are daily, covering **2021-01-04 through 2025-12-31**.

## Files

| File | Rows (incl. header) | Chelsea commodity_code in file | AgriFlow canonical |
|---|---|---|---|
| `bawang_merah_cleaned.csv` | 10,161 | `bawang_merah` | `bawang_merah` (direct match) |
| `bawang_putih_cleaned.csv` | 10,161 | `bawang_putih` | `bawang_putih` (direct match) |
| `cabe_rawit_cleaned.csv` | 10,160 | `cabe_rawit` | `cabai_rawit` (spelling normalization applied at load time) |
| `daging_ayam_cleaned.csv` | 10,161 | `daging_ayam` | `daging_ayam` (direct match) |
| `telur_ayam_cleaned.csv` | 10,161 | `telur_ayam` | `telur_ayam` (direct match) |
| `medium1_cleaned.csv` | 8,833 | `beras_medium_1` | `beras_medium` (grade aggregation — see mapping notes) |
| `medium2_cleaned.csv` | 8,897 | `beras_medium_2` | `beras_medium` (grade aggregation — see mapping notes) |
| `super1_cleaned.csv` | 10,160 | `beras_super_1` | `beras_premium` (grade aggregation — see mapping notes) |
| `super2_cleaned.csv` | 8,897 | `beras_super_2` | `beras_premium` (grade aggregation — see mapping notes) |

Total rows (excluding headers): **87,590**

## City coverage

8 Kota IHK Tier-1 (BPS wilayah codes):
`3509, 3510, 3529, 3571, 3573, 3574, 3577, 3578`

## Commodity code mapping notes

### Rice grade mapping (medium1/medium2 -> beras_medium, super1/super2 -> beras_premium)

PIHPS tracks two sub-grades of medium rice ("IR64 lokal" variants) and two sub-grades of
premium/super rice. AgriFlow's engine uses two canonical beras codes:

- `beras_medium`   — maps `beras_medium_1` AND `beras_medium_2`
- `beras_premium`  — maps `beras_super_1` AND `beras_super_2`

The mapping rationale: PIHPS medium grades correspond to Bapanas mapping_id 2 (`beras_medium`);
PIHPS super grades correspond to mapping_id 1 (`beras_premium`). The engine does not distinguish
sub-grades — it prices at canonical level. When both sub-grades exist for the same (date, city),
`load_price_history_csvs()` takes the **mean** price before returning (no data is dropped,
but the two sub-grade rows are averaged into one canonical row to preserve the UNIQUE constraint
on `(date, city_id, commodity_code)`).

### cabe_rawit spelling normalization

Chelsea's files use `cabe_rawit`; AgriFlow canonical is `cabai_rawit` (standard BI spelling).
The `load_price_history_csvs()` function applies this rename at read time.
`cabai_merah` (Cabai Merah Besar) is a **different commodity** — it is NOT in this dataset.

### Codes not yet in AgriFlow engine commodity table

None. After mapping, all codes (`bawang_merah`, `bawang_putih`, `cabai_rawit`, `daging_ayam`,
`telur_ayam`, `beras_medium`, `beras_premium`) exist in `sample_data/komoditas_constraints.csv`
and `db/schema.sql`'s commodity_code_map seed.

## Attribution

Data collected and cleaned by the AgriFlow TimesFM team:
- Chelsea Ayu (repo owner)
- Original upstream: PIHPS / Badan Pangan Nasional daily price panel

This vendored copy is used for **offline demo purposes only** while Supabase credentials
are not yet provisioned. The `ingest_to_postgres()` path in `db/price_ingest.py` provides
the live-ingest route once creds are available.
