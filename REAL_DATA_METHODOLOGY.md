# Real Data Methodology — Surplus/Deficit 2022

## Status per commodity

| Commodity | Status | Source | Tahun |
|---|---|---|---|
| `beras_premium` | REAL (derived) | BPS per-kab produksi + konsumsi + populasi | 2022 |
| `beras_medium` | REAL (derived, grade-split assumption 60/40) | same | 2022 |
| `cabai_merah` | REAL produksi (BPS Hortikultura); konsumsi proxy nasional (Kementan) | BPS Jatim Hortikul. + Kementan PDF | 2022 |
| `cabai_rawit` | REAL produksi (BPS Hortikultura); konsumsi proxy nasional (Kementan) | same | 2022 |
| `bawang_merah` | REAL produksi (BPS Hortikultura); konsumsi proxy nasional (Kementan) | same | 2022 |
| `bawang_putih` | REAL produksi (BPS Hortikultura); konsumsi proxy nasional (Kementan) | same | 2022 |
| `daging_ayam` | EXCLUDED — data tidak lengkap (broiler hilang; ayam petelur 2 kab) | — | PENDING |
| `telur_ayam` | EXCLUDED — telur petelur hanya 2 kab | — | PENDING |

---

## Reference year: 2022

All three beras inputs AND semua 5 hortikultura source files have 2022 data.
**2022** is selected as the reference year because:
- Beras: 2022 is the latest year where produksi, konsumsi per-kab, AND populasi are all
  present and plausible for all 38 kab/kota. (2025 populasi corrupted ~1000x.)
- Hortikultura: BPS Hortikultura files have `Produksi_2021` and `Produksi_2022` columns;
  2022 is the most recent available year.
- Konsumsi per-kapita hortikultura: Kementan Statistik Konsumsi Pangan 2024 provides
  2022 values in Tabel 4.6a (cabai) and 4.1a/4.2a (bawang).

---

## Data sources

### Beras (all BPS-grade, per-kabupaten)

| Dataset | File | Source | Unit |
|---|---|---|---|
| Produksi beras | `sample_data/bps_real/year_beras.csv` | BPS Jawa Timur | ton/tahun/kab |
| Konsumsi per kapita | `sample_data/bps_real/week_konsumsi_beras_perkapita.csv` | BPS Indonesia (Susenas) | kg/kapita/minggu |
| Populasi | `sample_data/bps_real/year_populasi_jatim.csv` | BPS Jawa Timur | jiwa |

### Hortikultura

| Dataset | File | Source | Unit | Konversi |
|---|---|---|---|---|
| Produksi cabai besar | `bps_real/cabai_besar.csv` | BPS Jatim Hortikul. | **KUINTAL**/tahun | ÷10 = ton |
| Produksi cabai keriting | `bps_real/cabai_keriting.csv` | same | KUINTAL/tahun | ÷10 = ton |
| Produksi cabai rawit | `bps_real/cabai_rawit.csv` | same | KUINTAL/tahun | ÷10 = ton |
| Produksi bawang merah | `bps_real/bawang_merah.csv` | same | KUINTAL/tahun | ÷10 = ton |
| Produksi bawang putih | `bps_real/bawang_putih.csv` | same | KUINTAL/tahun | ÷10 = ton |

**Satuan konfirmasi**: Total row cabai_besar 2022 = 851,445 kuintal = 85,145 ton → sesuai
BPS published figure Jatim. Konversi ÷10 (kuintal → ton) terverifikasi.

### Konsumsi per kapita hortikultura — NATIONAL PROXY (Kementan)

Sumber: **Statistik Konsumsi Pangan 2024**, Pusat Data dan Sistem Informasi Pertanian,
Kementerian Pertanian. Desember 2024.
URL: https://satudata.pertanian.go.id/assets/docs/publikasi/Buku_Statistik_Konsumsi_2024.pdf

| Komoditas | Tabel | Hal. | Nilai 2022 | Catatan |
|---|---|---|---|---|
| Cabai merah | 4.6a (Cabe merah/Chillies) | 30 | **1.909 kg/kapita/tahun** | Susenas per-kapita nasional |
| Cabai rawit | 4.6a (Cabe rawit/Cayenne pepper) | 30 | **2.073 kg/kapita/tahun** | same |
| Bawang merah | 4.1a (Bawang merah/Onion) | 25 | **3.024 kg/kapita/tahun** | same |
| Bawang putih | 4.2a (Bawang putih/Garlic) | 26 | **2.016 kg/kapita/tahun** | same |

**PROXY WARNING**: Angka ini adalah RATA-RATA NASIONAL dari Susenas. Tidak ada data konsumsi
per-kabupaten untuk hortikultura. Konsumsi aktual per kab bisa berbeda dari angka nasional
(terutama kota besar vs pedesaan, atau daerah produsen di mana konsumsi lokal bisa lebih tinggi).
Hasil surplus/deficit hortikultura harus dibaca dengan caveat ini.

---

## Derivation formula

### Beras

```
konsumsi_ton = avg_konsumsi_perkapita_kg_per_minggu × 52 × populasi / 1000
net_ton      = produksi_ton − konsumsi_ton
role         = "SURPLUS" if net_ton > 0 else "DEFICIT"
volume_tons  = abs(net_ton)
```

Per-kab BPS Susenas data digunakan untuk konsumsi beras (bukan proxy nasional).

### Hortikultura (cabai merah, cabai rawit, bawang merah, bawang putih)

```
produksi_ton  = (Produksi_2022 kuintal) / 10         # BPS file, kuintal -> ton
konsumsi_ton  = perkapita_kg_per_tahun × populasi_2022 / 1000  # Kementan national avg
net_ton       = produksi_ton − konsumsi_ton
role          = "SURPLUS" if net_ton > 0 else "DEFICIT"
volume_tons   = abs(net_ton)
```

Cabai merah = cabai_besar + cabai_keriting (dijumlahkan sebelum derivasi).

---

## Grade split beras: ASSUMPTION

60% net beras → `beras_premium`; 40% → `beras_medium`. Working assumption.

---

## Harga (2022 PIHPS median dari sample_data/price_history/)

| Komoditas | Harga IDR/kg | Sumber |
|---|---|---|
| `beras_premium` | 11,500 | median(super1=12,000; super2=11,000) PIHPS 2022 |
| `beras_medium` | 10,325 | median(medium1=10,650; medium2=10,000) PIHPS 2022 |
| `cabai_rawit` | 41,000 | cabe_rawit_cleaned.csv 2022 median, PIHPS |
| `bawang_merah` | 32,500 | bawang_merah_cleaned.csv 2022 median, PIHPS |
| `bawang_putih` | 20,750 | bawang_putih_cleaned.csv 2022 median, PIHPS |
| `cabai_merah` | 45,000 | **FLAGGED: komoditas_constraints.csv baseline** — cabai merah tidak ada di PIHPS dataset |

---

## harvest_age_days

| Role | Value | Rationale |
|---|---|---|
| SURPLUS | 28 | Typical post-harvest/milling age when komoditas leaves origin kab (conservative estimate) |
| DEFICIT | 0 | Convention: deficit nodes are demand points; age irrelevant |

---

## Name-to-kab_id mapping

**Beras source files**: menggunakan nama BPS full ("Kabupaten X" / "Kota X") →
strip prefix untuk match ke `kabupaten_jatim.csv` short name.

**Hortikultura source files**: menggunakan nama pendek tanpa prefix positional:
- Baris 0-28 (29 baris): Kabupaten, urutan kode BPS 3501 (Pacitan) s/d 3529 (Sumenep)
- Baris 29-37 (9 baris): Kota, urutan kode BPS 3571 (Kota Kediri) s/d 3579 (Kota Batu)
- Baris 38: "Total" — EXCLUDED

Semua 38 kab/kota Jatim ter-map tanpa exception untuk tahun 2022.

---

## Sanity check results (2022)

### Beras — top surplus kabupaten

| kab_id | Kabupaten | Net beras (ton) | Role |
|---|---|---|---|
| 3524 | Kab. Lamongan | +409,023 | SURPLUS |
| 3521 | Kab. Ngawi | +366,367 | SURPLUS |
| 3522 | Kab. Bojonegoro | +295,679 | SURPLUS |
| 3523 | Kab. Tuban | +184,507 | SURPLUS |
| 3519 | Kab. Madiun | +195,419 | SURPLUS |

### Cabai merah — top surplus

| kab_id | Kabupaten | Surplus (ton) |
|---|---|---|
| 3507 | Kab. Malang | ~22,328 |
| 3513 | Kab. Probolinggo | ~9,823 |
| 3510 | Kab. Banyuwangi | ~7,177 |

### Cabai rawit — top surplus

| kab_id | Kabupaten | Surplus (ton) |
|---|---|---|
| 3510 | Kab. Banyuwangi | ~100,709 |
| 3507 | Kab. Malang | ~81,866 |
| 3506 | Kab. Kediri | ~77,761 |

### Bawang merah — top surplus

| kab_id | Kabupaten | Surplus (ton) |
|---|---|---|
| 3518 | Kab. Nganjuk | ~190,610 |
| 3513 | Kab. Probolinggo | ~54,731 |
| 3507 | Kab. Malang | ~43,099 |

### Bawang putih

Seluruh 38 kab/kota DEFICIT. Jatim total produksi ~855 ton vs kebutuhan ~80,000+ ton.
(Jatim bukan produsen bawang putih; pasokan dari Temanggung/Brebes Jateng dan impor.)

Semua hasil ini sesuai ekspektasi geografis.

---

## Excluded

- **Daging ayam**: Data folder download berisi `daging_ayam_kampung.csv` dan
  `daging_ayam_petelur.csv`. Broiler (sumber utama produksi komersial) tidak ada.
  Data tidak representatif untuk routing engine. **Status: PENDING.**
- **Telur ayam**: `telur_ayam_petelur.csv` hanya 2 kabupaten ter-cover.
  **Status: PENDING.**
