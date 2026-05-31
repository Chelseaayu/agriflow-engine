# BPS Real Data — Provenance

Vendored from local download on 2026-05-31.
Original files downloaded by Hilmi Nur Ardian from BPS and BPS Jatim.

**Reference year for all commodities: 2022** (consistent snapshot — the latest year
present in ALL data sources simultaneously).

---

## Files in this directory

| File | Rows (excl. header) | Coverage | Unit |
|---|---|---|---|
| `year_beras.csv` | 190 | 38 kab/kota Jatim, 2021–2025, annual rice production | ton/tahun |
| `week_konsumsi_beras_perkapita.csv` | 190 | 38 kab/kota Jatim, 2021–2025, weekly per-capita rice consumption | kg/kapita/minggu |
| `year_populasi_jatim.csv` | 191 | 38 kab/kota Jatim, 2021–2025, annual population | jiwa |
| `cabai_besar.csv` | 39 (incl. Total) | 38 kab/kota Jatim, years 2021–2022 wide | **KUINTAL**/tahun |
| `cabai_keriting.csv` | 39 (incl. Total) | 38 kab/kota Jatim, years 2021–2022 wide | **KUINTAL**/tahun |
| `cabai_rawit.csv` | 39 (incl. Total) | 38 kab/kota Jatim, years 2021–2022 wide | **KUINTAL**/tahun |
| `bawang_merah.csv` | 39 (incl. Total) | 38 kab/kota Jatim, years 2021–2022 wide | **KUINTAL**/tahun |
| `bawang_putih.csv` | 39 (incl. Total) | 38 kab/kota Jatim, years 2021–2022 wide | **KUINTAL**/tahun |
| `Statistik_Konsumsi_2024.pdf` | — | Kementan PDF for per-kapita hortikultura consumption | — |

---

## Source attribution

### Produksi Beras (`year_beras.csv`)

- **Sumber**: BPS Provinsi Jawa Timur
- **Tabel**: "Produksi Beras Menurut Kabupaten/Kota — Tabel Statistik — BPS Jatim"
- **Tahun data**: 2021–2025
- **Satuan**: ton per tahun per kabupaten/kota

### Konsumsi Beras Per Kapita (`week_konsumsi_beras_perkapita.csv`)

- **Sumber**: BPS Indonesia (Susenas)
- **Tabel**: "Beras: Rata-rata Konsumsi Perkapita Seminggu Menurut Kelompok Padi-Padian Per Kab/Kota"
- **Tahun data**: 2021–2025
- **Satuan**: kg per kapita per minggu

### Populasi (`year_populasi_jatim.csv`)

- **Sumber**: BPS Jawa Timur
- **Tabel**: "Jumlah Penduduk per Kabupaten/Kota di Provinsi Jawa Timur"
- **Tahun data**: 2021–2025
- **Satuan**: jiwa (persons)

### Produksi Hortikultura (`cabai_besar/keriting/rawit`, `bawang_merah/putih`)

- **Sumber**: BPS Jawa Timur (Statistik Hortikultura)
- **Format**: Wide CSV, BOM UTF-8, kolom `Kabupaten, Produksi_2021, Produksi_2022`
- **Struktur baris**: Baris 0-28 = 29 Kabupaten (kode 3501-3529), Baris 29-37 = 9 Kota (3571-3579), Baris 38 = "Total" (EXCLUDED)
- **Satuan PENTING: KUINTAL** (bukan ton). Konversi: Produksi_2022 / 10 = ton.
  - Verifikasi: Total row cabai_besar 2022 = 851,445 kuintal = 85,145 ton — sesuai BPS published figure.
- **Kolom dipakai**: `Produksi_2022` saja (referensi tahun 2022)
- **NaN treatment**: treated as 0 (kab tidak ada produksi)

### Konsumsi Per Kapita Hortikultura — NATIONAL PROXY

- **Sumber**: Statistik Konsumsi Pangan 2024, Pusat Data dan Sistem Informasi Pertanian,
  Sekretariat Jenderal Kementerian Pertanian, Desember 2024
- **URL PDF**: https://satudata.pertanian.go.id/assets/docs/publikasi/Buku_Statistik_Konsumsi_2024.pdf
- **Dicatat**: 2026-05-31, file lokal `Statistik_Konsumsi_2024.pdf`

| Komoditas | Tabel | Halaman | Nilai 2022 | Satuan |
|---|---|---|---|---|
| Cabai merah (Chillies) | 4.6a | 30 | **1.909** | kg/kapita/tahun |
| Cabai rawit (Cayenne pepper) | 4.6a | 30 | **2.073** | kg/kapita/tahun |
| Bawang merah (Onion) | 4.1a | 25 | **3.024** | kg/kapita/tahun |
| Bawang putih (Garlic) | 4.2a | 26 | **2.016** | kg/kapita/tahun |

**CAVEAT**: Ini adalah konsumsi per-kapita NASIONAL dari Susenas. Tidak ada data konsumsi
per-kab untuk hortikultura (berbeda dengan beras yang ada data Susenas per-kab). Angka ini
dipakai sebagai proxy nasional; distribusi konsumsi riil antar kab mungkin berbeda.

---

## Harga (2022 PIHPS median)

| Komoditas | Harga IDR/kg | Sumber |
|---|---|---|
| `beras_premium` | 11,500 | Median super1+super2 PIHPS 2022 (sample_data/price_history/) |
| `beras_medium` | 10,325 | Median medium1+medium2 PIHPS 2022 |
| `cabai_rawit` | 41,000 | cabe_rawit_cleaned.csv PIHPS 2022 median |
| `bawang_merah` | 32,500 | bawang_merah_cleaned.csv PIHPS 2022 median |
| `bawang_putih` | 20,750 | bawang_putih_cleaned.csv PIHPS 2022 median |
| `cabai_merah` | 45,000 | **NOT in PIHPS** — menggunakan komoditas_constraints.csv baseline [FLAGGED] |

---

## Data quality notes

### 2025 population: CORRUPTED — do not use

The `year_populasi_jatim.csv` 2025 rows contain values ~1000x inflated compared to reality
(e.g., Kabupaten Kediri shows 1,702,262,000 instead of ~1,702,262). **Resolution**: use 2022
as reference year — all 38 kab complete and plausible for 2022.

### Daging & Telur: EXCLUDED — data tidak lengkap

- `daging_ayam_kampung.csv` / `daging_ayam_petelur.csv` dari folder horti: broiler tidak ada
  (hanya ayam kampung/petelur, bukan data produksi broiler yang relevan)
- `telur_ayam_petelur.csv`: hanya 2 kabupaten ter-cover (tidak representatif 38 kab)
- Status: **PENDING**

### Cabai merah: harga tidak tersedia di PIHPS

PIHPS (sample_data/price_history/) tidak mencakup cabai merah (besar/keriting) —
hanya cabe_rawit. Harga 45,000 IDR/kg diambil dari komoditas_constraints.csv baseline
(synthetic). Jika data PIHPS/Bapanas 2022 untuk cabai merah tersedia, update price.

---

## Derivation script

`sample_data/bps_real/derive_surplus_deficit_2022.py`

Output: `sample_data/surplus_deficit_real.csv` (228 rows = 38 kab × 6 commodity-grades)
