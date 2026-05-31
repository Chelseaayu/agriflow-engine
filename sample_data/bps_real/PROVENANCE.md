# BPS Real Data — Provenance

Vendored from local download on 2026-05-31.
Original files downloaded by Hilmi Nur Ardian from BPS and BPS Jatim.

---

## Files in this directory

| File | Rows (excl. header) | Coverage |
|---|---|---|
| `year_beras.csv` | 190 | 38 kab/kota Jatim, 2021–2025, annual rice production (ton) |
| `week_konsumsi_beras_perkapita.csv` | 190 | 38 kab/kota Jatim, 2021–2025, weekly per-capita rice consumption (kg/week) |
| `year_populasi_jatim.csv` | 191 | 38 kab/kota Jatim, 2021–2025, annual population |

---

## Source attribution (from Link Dataset.docx, Table 1 & Table 0)

### Produksi Beras (`year_beras.csv`)

- **Sumber**: BPS Provinsi Jawa Timur
- **Tabel**: "Produksi Beras Menurut Kabupaten/Kota — Tabel Statistik — Badan Pusat Statistik Provinsi Jawa Timur"
- **Tahun data**: 2021–2025
- **URL**: https://jatim.bps.go.id/ (Tabel Statistik, Produksi Beras)
- **Satuan**: ton per tahun per kabupaten/kota

### Konsumsi Beras Per Kapita (`week_konsumsi_beras_perkapita.csv`)

- **Sumber**: BPS Indonesia
- **Tabel**: "Beras: Rata-rata Konsumsi Perkapita Seminggu Menurut Kelompok Padi-Padian Per Kabupaten/Kota — Tabel Statistik — Badan Pusat Statistik Indonesia"
- **Tahun data**: 2021–2025
- **URL**: https://www.bps.go.id/ (Tabel Statistik, Konsumsi Per Kapita)
- **Satuan**: kg per kapita per minggu

### Populasi (`year_populasi_jatim.csv`)

- **Sumber**: BPS Jawa Timur
- **Tabel**: "Jumlah Penduduk, Laju Pertumbuhan Penduduk, Distribusi Persentase Penduduk, Kepadatan Penduduk, Rasio Jenis Kelamin Penduduk Menurut Kabupaten/Kota di Provinsi Jawa Timur — Tabel Statistik — Badan Pusat Statistik Provinsi Jawa Timur"
- **Tahun data**: 2021–2025
- **Satuan**: jiwa (persons)

---

## Data quality notes

### 2025 population: CORRUPTED — do not use

The `year_populasi_jatim.csv` 2025 rows contain values ~1000x inflated compared to reality
(e.g., Kabupaten Kediri shows 1,702,262,000 instead of ~1,702,262). This appears to be a
data-entry error in the source file where the unit was recorded as "jiwa" but the figures
correspond to the national population, not the kabupaten.

**Resolution**: `surplus_deficit_real.csv` uses **2024** as the reference year across all
three datasets, where all 38 kabupaten have consistent, plausible values.

### 2025 production and consumption: available but not used

Production (`year_beras.csv`) and consumption (`week_konsumsi_beras_perkapita.csv`) do contain
plausible 2025 values across all 38 kabupaten. However, because the matching population file
for 2025 is corrupted, 2024 is used for the full derivation.

---

## Re-derivation

All three files are offline-reproducible. The derivation script is
`sample_data/bps_real/` (these source files) + the methodology in
`REAL_DATA_METHODOLOGY.md` at the project root.
