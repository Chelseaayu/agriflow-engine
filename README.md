# AgriFlow Matching Engine

> **Sub-national pangan matching engine pertama di Indonesia.**
> Algoritma 4-lapis hybrid yang menghubungkan kabupaten surplus dengan defisit menggunakan stable matching, multi-objective scoring 5 dimensi, dan equity multiplier untuk kabupaten tertinggal — semua untuk komoditas pangan tingkat kabupaten.

[![Tests](https://img.shields.io/badge/tests-106%2F106%20passing-brightgreen)]()
[![Latency](https://img.shields.io/badge/p99%20latency-1.4ms%20%E2%86%92%2055.5ms-blue)]()
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)]()
[![Status](https://img.shields.io/badge/status-provincial--ready-success)]()

Submisi **PIDI DIGDAYA × Hackathon 2026** — Bank Indonesia.
Problem Statement #2: Platform Matching Demand-Supply Antarwilayah.

---

## Daftar Isi

- [Apa Ini?](#apa-ini)
- [Quick Start (5 menit)](#quick-start-5-menit)
- [Arsitektur 4-Lapis](#arsitektur-4-lapis)
- [Equity Multiplier (Kalibrasi BPS 2024)](#equity-multiplier-kalibrasi-bps-2024)
- [19 Skenario Edge Case](#19-skenario-edge-case)
- [API Usage](#api-usage)
- [Performance & Validation](#performance--validation)
- [Data Sources](#data-sources)
- [Project Structure](#project-structure)
- [Development Guide](#development-guide)
- [Status & Roadmap](#status--roadmap)
- [Documentation](#documentation)
- [License & Credits](#license--credits)

---

## Apa Ini?

**Bayangkan Uber, tapi untuk cabai dan bawang merah.**

Setiap hari, Indonesia kehilangan Rp 213-551 triliun pangan karena food loss & waste — 40% di distribusi, bukan produksi. Petani di Sampang membuang cabai karena harga jatuh, sementara pasar Surabaya melonjak 200% karena kelangkaan. Pemda baru tahu krisis 2-3 minggu kemudian.

AgriFlow Matching Engine memecahkan ini dengan 6 dimensi yang Uber tidak punya:

| Dimensi | Penjelasan |
|---|---|
| **Perishability** | Cabai busuk dalam 5 hari, beras tahan 180 hari — engine hitung shelf life |
| **Equity** | Kabupaten tertinggal IPM rendah (Sampang 66.72) dapat boost +30% |
| **Climate** | Banjir di rute = re-route otomatis |
| **Volume** | 1 surplus bisa di-split ke banyak deficit |
| **Stable Matching** | Guarantee fairness via Gale-Shapley (Nobel Prize Economics 2012) |
| **Two-tier Confidence** | Data harian PIHPS (Tier 1) pakai algoritma ketat; data mingguan Bapanas (Tier 2) pakai algoritma fleksibel |

**Status:** Production-ready untuk skala provinsial (38 kab Jatim) — 106/106 tests pass dalam 0.16s, latency p99 1.4ms (sample) - 55.5ms (stress 361×361).

---

## Quick Start (5 menit)

### Prasyarat

- Python 3.10+
- pip
- ~50MB disk space

### Install

```bash
git clone https://github.com/masterA88/agriflow_engine.git
cd agriflow_engine
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
pip install -r requirements.txt
```

### Verifikasi (semua harus sukses)

```bash
# 1. Generate sample data — 38 kab × 19 komoditas Jatim
python sample_data/generate_sample_data.py
# Expected: 5 CSV generated (kabupaten_jatim.csv, komoditas_constraints.csv,
#           surplus_deficit.csv, weather_forecast.csv, historical_price_stats.csv)

# 2. Run all tests (106 tests)
pytest tests/ -v
# Expected: 106 passed in <1s

# 3. Run end-to-end demo
python examples/run_demo.py
# Expected: ~32 matches, gross arbitrage ~Rp 16 miliar, latency ~1.5ms

# 4. Run latency benchmark
python benchmarks/latency.py
# Expected: highest p99 < 60ms (margin >88% vs 500ms target)
```

Kalau langkah 2 atau 3 gagal, lihat [Troubleshooting](#troubleshooting) di bawah.

---

## Arsitektur 4-Lapis

```
Input: surplus_nodes[], deficit_nodes[], LogisticsContext, weather, historical_prices

  ┌─────────────────────────────────────────────────────────────────┐
  │ LAYER 0 — Tier Classification (constraints.determine_tier)      │
  │   Klasifikasi setiap kab: Tier 1 HIGH (8 kota IHK PIHPS) atau   │
  │   Tier 2 MEDIUM (30 kab non-IHK Bapanas).                       │
  │   Latency: <1ms (set lookup).                                   │
  └─────────────────────────────────────────────────────────────────┘
                            ↓
  ┌─────────────────────────────────────────────────────────────────┐
  │ LAYER 1 — Hard Constraints (constraints.generate_candidates)    │
  │   9 rules filter: komoditas match, distance≤max, age≤shelf,     │
  │   volume≥min, no self-match, emergency mode, pemda override,    │
  │   Bulog split, BBM-aware distance shrink.                       │
  │   Output: candidate pairs (top-K per surplus by jarak).         │
  │   Latency: <50ms untuk 38×19 (~25k pasang potensial).           │
  └─────────────────────────────────────────────────────────────────┘
                            ↓
  ┌─────────────────────────────────────────────────────────────────┐
  │ LAYER 2 — Multi-Objective Scoring (scoring.compute_score)       │
  │   5-dimensi weighted: Distance 22% / Volume 22% / Price 22% /   │
  │   Perishability 18% / Climate 16%.                              │
  │   3 weight schemes: DEFAULT, RAMADAN, IMPORT_POLICY.            │
  │   Output: base_score 0-100 per pair.                            │
  └─────────────────────────────────────────────────────────────────┘
                            ↓
  ┌─────────────────────────────────────────────────────────────────┐
  │ LAYER 3 — Equity-Weighted Allocation (allocation.allocate)      │
  │   Final = base × equity_multiplier(IPM_deficit).                │
  │   Tier 1↔Tier 1 → Modified Gale-Shapley (Nobel 2012).           │
  │   Cross-tier / Tier 2 → Greedy with equity priority.            │
  │   Output: MatchResult[] dengan confidence label.                │
  └─────────────────────────────────────────────────────────────────┘
                            ↓
  ┌─────────────────────────────────────────────────────────────────┐
  │ POST-PROCESSING (engine.run_matching)                           │
  │   Tag flags (RAMADAN_SPIKE, EQUITY_BOOST_30, MADURA_CLUSTER,    │
  │   STALE_DATA_24H, HUMANITARIAN_PRIORITY, VOLUME_MISMATCH).      │
  │   Identifikasi unmatched + external_opportunities (ekspor).     │
  └─────────────────────────────────────────────────────────────────┘

Output: MatchingReport(matches, unmatched_*, warnings, run_metadata)
```

**Why 4-layer?** Setiap layer bisa dioptimasi independent, testable secara isolated, dan early-exit di Layer 1 menghemat compute Layer 2/3 yang lebih mahal.

---

## Equity Multiplier (Kalibrasi BPS 2024)

Threshold dikalibrasi sesuai distribusi IPM 2024 BPS Jatim sehingga klaim "+30% boost untuk kab tertinggal" konkret applicable:

| IPM Range | Multiplier | Boost | Kab/Kota Jatim |
|---|---|---|---|
| `IPM < 68` | **1.30** | **+30%** | Sampang (66.72), Bangkalan (67.70) |
| `68 ≤ IPM < 72` | 1.15 | +15% | Sumenep, Probolinggo (kab), Bondowoso, Lumajang, Pamekasan, Pacitan, Pasuruan (kab), Situbondo, Jember, Madiun (kab) |
| `72 ≤ IPM < 78` | 1.05 | +5% | Bojonegoro, Banyuwangi, Tulungagung, Malang (kab), Magetan, Gresik, Mojokerto (kab), Lamongan, Tuban, Ngawi, Kediri (kab), dll |
| `IPM ≥ 78` | 1.00 | (no boost) | Sidoarjo, Kota Batu, Kota Surabaya, Kota Malang, Kota Kediri, Kota Madiun, dll |

**Mengapa kalibrasi:** Threshold v9 lama (`<65 → 1.30`) tidak pernah ter-trigger karena IPM terendah Jatim 2024 = Sampang 66.72. v10 menggeser threshold sehingga klaim "+30% boost" demonstrably valid.

**Update IPM tahunan:** Saat BPS publish IPM baru (biasanya BRS Desember), edit di [`sample_data/generate_sample_data.py:KABUPATEN_DATA`](sample_data/generate_sample_data.py) sebagai source of truth, lalu mirror ke [`data_sources/bps.py:IPM_2024_JATIM`](data_sources/bps.py).

---

## 19 Skenario Edge Case

5 kategori, 19 skenario, semua tervalidasi pytest. Detail lengkap di [`docs/AUDIT_v10.md`](docs/AUDIT_v10.md) dan `AgriFlow_v10.docx` Section 5.5.5.

### Kategori A — Volume (4 skenario)

| Kode | Skenario | Test |
|---|---|---|
| A1 | Surplus 1-to-many (1 surplus split ke beberapa deficit) | `TestA1_OneToMany` |
| A2 | Many-to-1 (multiple surplus untuk 1 deficit besar) | `TestA2_ManyToOne` |
| A3 | Volume mismatch drastis (<20% ratio → flag warning) | `TestA3_VolumeMismatchDrastis` |
| A4 | Zero demand (suggest external opportunity) | `TestA4_ZeroDemand` |

### Kategori B — Spasial (3 skenario)

| Kode | Skenario | Test |
|---|---|---|
| B1 | Cross-tier match (Tier 1 ↔ Tier 2) | `TestB1_CrossTier` |
| B2 | Long distance (jarak > max_distance_km → REJECT) | `TestB2_LongDistance` |
| B3 | Cluster Madura (4 kab semua surplus → ekspor) | `TestB3_ClusterMadura` |

### Kategori C — Temporal (3 skenario)

| Kode | Skenario | Test |
|---|---|---|
| C1 | Ramadan/Idul Fitri spike (H-21 to H-1, RAMADAN_WEIGHTS) | `TestC1_RamadanSpike` |
| C2 | Pasca panen raya (oversupply, multiple match) | `TestC2_PostHarvest` |
| C3 | Stale data >24h (confidence drop bertingkat HIGH→MEDIUM→LOW) | `TestC3_StaleData` |

### Kategori D — Disrupsi (5 skenario)

| Kode | Skenario | Test |
|---|---|---|
| D1 | Banjir rute (BMKG hujan >50mm → climate_score 0.3) | `TestD1_BanjirRute` |
| D2 | Komoditas hampir rusak (harvest age + transit > shelf) | `TestD2_KomoditasRusak` |
| D3 | Harga anomali (>3σ dari rolling median → exclude) | `TestD3_HargaAnomali` |
| D4 | Erupsi gunung (PVMBG MAGMA → UNREACHABLE) | `TestD4_ErupsiGunung` |
| D5 | Banjir multi-kab (BNPB DIBI → emergency mode) | `TestD5_BanjirMultiKab` |

### Kategori E — Politis & Kebijakan (5 skenario)

| Kode | Skenario | Test |
|---|---|---|
| E1 | Equity tie-break (IPM lebih rendah menang otomatis) | `TestE1_EquityTieBreak` |
| E2 | Pemda override (`do_not_export_<komoditas>` flag) | `TestE2_PemdaOverride` |
| E3 | Bulog priority (60% reserve, sisa 40% private) | `TestE3_BulogPriority` |
| E4 | Import policy aktif (IMPORT_POLICY_WEIGHTS, price weight ↓) | `TestE4_ImportPolicy` |
| E5 | BBM naik (max_distance shrink, logistics cost ↑) | `TestE5_BBMNaik` |

---

## API Usage

### Programmatic API

```python
from matching_engine import (
    run_matching, SupplyNode, DemandNode,
    Kabupaten, Tier, Commodity, LogisticsContext,
)

# Setup kabupaten (real koordinat & IPM 2024 BPS)
kediri = Kabupaten(
    id="3506", nama="Kediri",
    latitude=-7.796, longitude=112.170,
    ipm=74.50, tier=Tier.MEDIUM,
)
surabaya = Kabupaten(
    id="3578", nama="Kota Surabaya",
    latitude=-7.2575, longitude=112.7521,
    ipm=84.69, tier=Tier.HIGH,
)

# Setup komoditas (constraint per komoditas)
cabai = Commodity(
    code="cabai_merah", nama="Cabai Merah Besar",
    max_distance_km=200, min_viable_tons=1.0,
    max_fresh_age_days=5,
)

# Run matching
report = run_matching(
    surplus_nodes=[
        SupplyNode(kediri, cabai, volume_tons=80, price_per_kg=30000),
    ],
    deficit_nodes=[
        DemandNode(surabaya, cabai, volume_tons=80, price_per_kg=60000),
    ],
    logistics=LogisticsContext(),
)

# Inspect hasil
for m in report.matches:
    print(f"{m.surplus.kabupaten.nama} → {m.deficit.kabupaten.nama}")
    print(f"  Volume: {m.matched_volume_tons}t @ {m.distance_km:.0f}km")
    print(f"  Score: {m.final_score:.1f} (base {m.base_score:.1f} × {m.equity_multiplier})")
    print(f"  Confidence: {m.confidence.value}, Flags: {m.flags}")

# Output:
# Kediri → Kota Surabaya
#   Volume: 80.0t @ 65km
#   Score: 89.5 (base 89.5 × 1.0)
#   Confidence: MEDIUM, Flags: []

print(f"\nLatency: {report.run_metadata['latency_ms']}ms")
print(f"Candidate pairs evaluated: {report.run_metadata['candidate_pairs_evaluated']}")
print(f"Warnings: {len(report.warnings)}")
```

### Advanced — Skenario Override

```python
from matching_engine.constraints import set_bulog_procurement
from datetime import datetime

# Skenario E3: Bulog procurement aktif untuk Madiun
set_bulog_procurement({"3519"})

# Skenario E4: Import policy aktif (bobot price diturunkan)
report = run_matching(
    surplus_nodes=[...],
    deficit_nodes=[...],
    import_policy_active=True,  # IMPORT_POLICY_WEIGHTS
)

# Skenario C1: Force Ramadan mode untuk testing
report = run_matching(
    surplus_nodes=[...],
    deficit_nodes=[...],
    reference_date=datetime(2026, 3, 6),  # H-14 Idul Fitri 2026
)

# Skenario E5: BBM naik 20%
from matching_engine.models import LogisticsContext
report = run_matching(
    surplus_nodes=[...],
    deficit_nodes=[...],
    logistics=LogisticsContext(
        bbm_price_idr_per_liter=12000,
        bbm_price_baseline=10000,
    ),
)
```

### Advanced — Force Algorithm Strategy

```python
# Force stable matching (Tier 1 algorithm)
report = run_matching(..., force_strategy="stable")

# Force greedy (Tier 2 algorithm) untuk testing
report = run_matching(..., force_strategy="greedy")

# Auto-detect (default): Tier 1↔Tier 1 pairs → stable, else → greedy
report = run_matching(...)
```

---

## Performance & Validation

### Test Suite

```bash
$ pytest tests/ --tb=short
============================= test session starts =============================
collected 106 items

tests/test_layer0_tier.py ................                           [ 15%]
tests/test_layer1_constraints.py ...................                 [ 33%]
tests/test_layer2_scoring.py .......................                 [ 54%]
tests/test_layer3_allocation.py ..............                       [ 67%]
tests/test_scenarios_disruption.py .........                         [ 76%]
tests/test_scenarios_political.py ........                           [ 83%]
tests/test_scenarios_spatial.py ......                               [ 89%]
tests/test_scenarios_temporal.py .......                             [ 96%]
tests/test_scenarios_volume.py ....                                  [100%]

============================= 106 passed in 0.16s =============================
```

### Latency Benchmark

```bash
$ python benchmarks/latency.py
```

| Configuration | N (s × d) | p50 | p95 | p99 | Max |
|---|---|---|---|---|---|
| Sample data CSV (realistic) | 40 × 33 | 0.99 ms | 1.26 ms | 1.38 ms | 1.42 ms |
| Synthetic full Jatim (38×19) | 361 × 361 | 48.37 ms | 53.67 ms | 55.53 ms | 58.43 ms |
| Stress 100×100 (national scale) | 100 × 100 | 12.62 ms | 14.82 ms | 15.51 ms | 15.65 ms |
| Stress 200×200 | 200 × 200 | 25.47 ms | 26.92 ms | 27.54 ms | 27.76 ms |

**Verdict:** PASS — semua p99 < 500ms target. Highest p99 = 55.53ms (margin 88.9%).

### National Scale (Indonesia 514 kab)

⚠ **HONEST DISCLOSURE:** Engine v10 saat ini BELUM siap untuk produksi nasional 514 kab. Lihat [`docs/AUDIT_v10.md`](docs/AUDIT_v10.md) Section 3.2 untuk detail. Optimization roadmap (spatial indexing, per-provinsi batching, parallel) sudah ter-quantify untuk Y2-Y3.

```bash
$ python benchmarks/national_scale.py
```

| Scale | Workload | p99 | vs target |
|---|---|---|---|
| Provinsi Jatim baseline | 333×389 | **14.2ms** | ✅ 35× under |
| Multi-provinsi (100 kab) | 948×952 | **94.5ms** | ✅ 5× under |
| Setengah Indonesia (250 kab) | 2326×2424 | **541.8ms** | ⚠ 1.08× over |
| **Full Indonesia (514 kab)** | **4859×4907** | **2223.3ms** | ❌ **4.4× over** |

---

## Data Sources

8 connector dengan dual-mode (mock CSV + live API), graceful fallback:

| Connector | Sumber | Frekuensi | Auth | Tier |
|---|---|---|---|---|
| [`pihps_bi.py`](data_sources/pihps_bi.py) | Bank Indonesia PIHPS | Harian (cut-off 13:00 WIB) | Tidak ada (scrape publik) | Tier 1 |
| [`bapanas.py`](data_sources/bapanas.py) | Panel Harga Bapanas | Mingguan (Senin) | Tidak ada | Tier 2 |
| [`bps.py`](data_sources/bps.py) | BPS WebAPI (IPM, produksi) | Tahunan (BRS Desember) | API key gratis | Both |
| [`bmkg.py`](data_sources/bmkg.py) | BMKG / Open-Meteo (cuaca) | 3-6 jam refresh | Tidak ada (Open-Meteo) | Both |
| [`pvmbg.py`](data_sources/pvmbg.py) | PVMBG MAGMA (gunung api) | Realtime saat status berubah | Tidak ada | Both |
| [`bnpb.py`](data_sources/bnpb.py) | BNPB DIBI (bencana) | Realtime | Tidak ada | Both |
| [`google_maps.py`](data_sources/google_maps.py) | Google Routes / OSRM fallback | Realtime per request | Google API key (paid) / OSRM gratis | Both |
| [`hijri_calendar.py`](data_sources/hijri_calendar.py) | Aladhan API + hardcoded | Statis | Tidak ada | Both |

### Fail-safe Strategy

- Live API gagal → fallback ke mock CSV / hardcoded data
- Weather data tidak tersedia → climate_score = 0.7 (neutral)
- BPS API gagal → fallback ke `IPM_2024_JATIM` hardcoded
- BMKG butuh adm4 mapping yang tidak ada → auto-fallback ke Open-Meteo
- OSRM down → haversine geodesic + asumsi 60 km/h

---

## Project Structure

```
agriflow_engine/
├── matching_engine/         # Core engine (5 modules, ~1000 lines)
│   ├── __init__.py          # Public API
│   ├── models.py            # Dataclasses (Kabupaten, Commodity, MatchResult, ...)
│   ├── constraints.py       # Layer 0 + Layer 1 (9 hard constraints)
│   ├── scoring.py           # Layer 2 (5-dim multi-objective scoring)
│   ├── allocation.py        # Layer 3 (Gale-Shapley + Greedy + Equity)
│   └── engine.py            # Main orchestrator + 19 skenario handlers
├── data_sources/            # 8 connector dual-mode (mock + live)
│   ├── pihps_bi.py          # Tier 1 PIHPS BI
│   ├── bapanas.py           # Tier 2 Bapanas
│   ├── bps.py               # IPM 2024 + produksi BPS
│   ├── bmkg.py              # Cuaca BMKG/Open-Meteo
│   ├── pvmbg.py             # Erupsi gunung PVMBG MAGMA
│   ├── bnpb.py              # Bencana BNPB DIBI
│   ├── google_maps.py       # Routing Google/OSRM
│   └── hijri_calendar.py    # Ramadan/Idul Fitri Aladhan
├── sample_data/             # CSV 38 kab × 19 komoditas Jatim
│   ├── generate_sample_data.py  # Source of truth — regenerate CSV
│   ├── loader.py                # CSV → engine objects
│   ├── kabupaten_jatim.csv      # 38 kab + IPM 2024 + koordinat
│   ├── komoditas_constraints.csv  # 19 komoditas + spec
│   ├── surplus_deficit.csv      # 73 row sample workload
│   ├── weather_forecast.csv     # 10 route forecast
│   └── historical_price_stats.csv  # 19 commodity rolling stats
├── tests/                   # 106 pytest test
│   ├── conftest.py          # Fixtures (17 kab Jatim + factory)
│   ├── test_layer0_tier.py             # 16 test (tier classification)
│   ├── test_layer1_constraints.py      # 19 test (haversine + viability + Bulog)
│   ├── test_layer2_scoring.py          # 23 test (5-dim scoring + weight schemes)
│   ├── test_layer3_allocation.py       # 14 test (equity + stable + greedy)
│   ├── test_scenarios_volume.py        # 4 test (A1-A4)
│   ├── test_scenarios_spatial.py       # 6 test (B1-B3)
│   ├── test_scenarios_temporal.py      # 7 test (C1-C3)
│   ├── test_scenarios_disruption.py    # 9 test (D1-D5)
│   └── test_scenarios_political.py     # 8 test (E1-E5)
├── examples/
│   └── run_demo.py          # End-to-end demo dengan output formatted
├── benchmarks/
│   ├── latency.py           # Multi-config provincial benchmark
│   └── national_scale.py    # National scale stress test (514 kab)
├── docs/
│   ├── generate_v10_docx.py # Proposal v10 docx generator
│   └── AUDIT_v10.md         # Audit lengkap (consistency + national scale analysis)
├── README.md                # This file
├── requirements.txt         # Python dependencies
└── venv/                    # (gitignored) virtual env
```

---

## Development Guide

### Setup Development Environment

```bash
git clone https://github.com/masterA88/agriflow_engine.git
cd agriflow_engine
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
pip install python-docx  # untuk regenerate proposal docx
```

### Workflow

1. **Edit code** di `matching_engine/` atau `data_sources/`
2. **Run test** sebelum commit: `pytest tests/ -v`
3. **Update sample data** kalau ubah threshold/komoditas: `python sample_data/generate_sample_data.py`
4. **Run demo** untuk smoke test: `python examples/run_demo.py`
5. **Run benchmark** kalau perubahan di hot path: `python benchmarks/latency.py`
6. **Regenerate proposal** kalau perubahan di logic: `python docs/generate_v10_docx.py`

### Add New Skenario

1. Tambah test class di file yang sesuai (mis. `tests/test_scenarios_volume.py`)
2. Tambah behavior di `matching_engine/engine.py` post-processing atau Layer yang relevan
3. Update `AgriFlow_v10.docx` Section 5.5.5 (regenerate via `docs/generate_v10_docx.py`)
4. Pastikan `pytest tests/ -v` masih PASS

### Add New Komoditas

1. Tambah row di [`sample_data/generate_sample_data.py:KOMODITAS_DATA`](sample_data/generate_sample_data.py)
2. Tambah row di [`matching_engine/constraints.py:COMMODITY_SPECS`](matching_engine/constraints.py) (samakan max_distance/min_viable/max_fresh_age)
3. Run `python sample_data/generate_sample_data.py` untuk regenerate CSV
4. Update assertion di test kalau komoditas count check

### Update IPM Tahunan (saat BPS publish data baru)

1. Edit [`sample_data/generate_sample_data.py:KABUPATEN_DATA`](sample_data/generate_sample_data.py) (source of truth)
2. Mirror ke [`data_sources/bps.py:IPM_2024_JATIM`](data_sources/bps.py)
3. Run `python sample_data/generate_sample_data.py` untuk regenerate CSV
4. Re-evaluate equity threshold di [`matching_engine/allocation.py:38`](matching_engine/allocation.py) — apakah masih meaningful trigger untuk distribusi baru?
5. Run `pytest tests/ -v` — beberapa test mungkin perlu update kalau IPM bergeser

---

## Status & Roadmap

### Current Status: ✅ Provincial-Ready (Jatim)

- [x] 4-layer architecture implemented
- [x] 19 skenario edge case handled
- [x] 106/106 tests passing
- [x] Latency p99 1.4ms (sample) - 55.5ms (stress)
- [x] Equity multiplier kalibrasi BPS 2024 — Sampang & Bangkalan menerima +30% boost
- [x] 8 data source connector dual-mode
- [x] Cross-platform demo (Windows/Linux/Mac)
- [x] Reproducible documentation generator

### Roadmap to National Scale (Y2-Y3)

⚠ **Honest disclosure:** Engine v10 saat ini BELUM siap untuk produksi nasional 514 kab. p99 untuk full Indonesia = 2.2 detik (4.4× over 500ms target).

**Optimization plan** (lihat [`docs/AUDIT_v10.md`](docs/AUDIT_v10.md) Section 6):

| Quick Win | Effort | Impact |
|---|---|---|
| Fix double-haversine bug di `generate_candidates` | 1 jam | 30-40% speedup Layer 1 |
| Add geohash precision-5 spatial pre-filter | 1-2 hari | 25-50× speedup Layer 1 |
| Multiprocessing per komoditas | 2-3 hari | Up to 19× speedup |
| Distance matrix precompute (Redis cache) | 4 jam | 5-10× speedup |
| Per-provinsi batching | 1 minggu | 5-15× speedup |

**Combined estimate:** ~100-200× speedup → bring p99 dari 2200ms ke ~10-20ms untuk 514 kab nasional.

### Data/Coverage Expansion (Y2)

- [ ] `TIER_1_KOTA_IHK`: 8 kota Jatim → ~90 kota IHK Indonesia
- [ ] `IPM_2024_JATIM` → `IPM_2024_INDONESIA` (514 kab/kota)
- [ ] Cluster definitions: Madura → 10-20 cluster nasional
- [ ] `GUNUNG_KABUPATEN_MAP`: 6 gunung Jatim → 130+ gunung api Indonesia
- [ ] Sample data: 38 kab → 514 kab synthetic + real

### Architectural Expansion (Y2-Y3)

- [ ] Inter-island logistics (transport mode: truck/ferry/cargo plane)
- [ ] Equity threshold recalibration nasional (range IPM 50-85)
- [ ] CI/CD pipeline (GitHub Actions: pytest + benchmark assertions)
- [ ] FastAPI wrapper untuk REST API production
- [ ] Hybrid stable+greedy untuk skenario campuran tier
- [ ] LLM integration (Gemini + Sahabat-AI Bahasa Daerah)

---

## Documentation

| Document | Lokasi | Deskripsi |
|---|---|---|
| **Proposal v10** | [`docs/AgriFlow_v10.docx`](docs/AgriFlow_v10.docx) | Proposal lengkap 14 section: business + technical |
| **Audit v10** | [`docs/AUDIT_v10.md`](docs/AUDIT_v10.md) | Consistency check + national scale analysis |
| **README** | This file | Quick reference + getting started |
| **Generator script** | [`docs/generate_v10_docx.py`](docs/generate_v10_docx.py) | Regenerate proposal docx dari source |
| **Code comments** | All `.py` files | Inline docstrings dengan reference ke proposal section |

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'matching_engine'"

Make sure di project root saat run script:
```bash
cd agriflow_engine
python examples/run_demo.py
```

Atau install sebagai package:
```bash
pip install -e .  # editable install (kalau pyproject.toml ada)
```

### Demo crash di Windows: "UnicodeEncodeError: 'charmap' codec"

v10 sudah include UTF-8 fix. Pastikan pakai versi terbaru:
```bash
git pull
```

Atau set env variable manual:
```bash
set PYTHONIOENCODING=utf-8
python examples/run_demo.py
```

### "FileNotFoundError: sample_data/kabupaten_jatim.csv"

CSV belum di-generate. Run dulu:
```bash
python sample_data/generate_sample_data.py
```

### pytest collect 0 items

Pastikan run dari project root, bukan dari `tests/`:
```bash
cd agriflow_engine  # not cd agriflow_engine/tests
pytest tests/
```

---

## License & Credits

**Lisensi:** Hackathon submission. Code internal AgriFlow team.

**Credits:**
- **Algoritma:** Gale-Shapley Stable Matching (Nobel Prize Economics 2012, Roth & Shapley)
- **Inspirasi platform:** eNAM (India), MealConnect (Feeding America), FEWS NET (USAID), Uber matching pattern, Food Drop Indiana
- **Data sumber:** Bank Indonesia (PIHPS), Bapanas (Panel Harga), BPS (BRS Desember 2024 IPM), BMKG, PVMBG MAGMA, BNPB DIBI

**Tim AgriFlow:** Hackathon DIGDAYA × PIDI 2026.

**Citing:**
```
AgriFlow Team. (2026). AgriFlow Matching Engine v10.0:
Sub-National Pangan Matching dengan Stable Matching + Equity Multiplier.
PIDI DIGDAYA × Hackathon 2026, Bank Indonesia.
```

---

## Pertanyaan & Kontak

- Issue tracker: GitHub Issues (this repo)
- Proposal lengkap: `AgriFlow_v10.docx` (parent folder)
- Audit teknis: [`docs/AUDIT_v10.md`](docs/AUDIT_v10.md)

**Deteksi. Prediksi. Distribusi. Untuk Semua.**
*AgriFlow — Powered by World-First AI Matching Engine for Sub-National Food Distribution.*
