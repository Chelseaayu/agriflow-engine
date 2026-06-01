Language / Bahasa: [English](./README.en.md) · **Bahasa Indonesia**

<h1 align="center">AgriFlow</h1>

<p align="center">
  <strong>AI-Powered Food Security Intelligence Platform</strong><br/>
  <em>Platform Matching Demand–Supply Pangan Antarwilayah</em>
</p>

<p align="center"><b>Deteksi · Prediksi · Distribusi</b></p>

<p align="center">
  <img src="https://img.shields.io/badge/PIDI-DIGDAYA%20%C3%97%20Hackathon%202026-1B5E20?style=for-the-badge" alt="Hackathon"/>
  <img src="https://img.shields.io/badge/Problem%20Statement-2%20Matching%20Demand–Supply-4CAF50?style=for-the-badge" alt="PS"/>
  <img src="https://img.shields.io/badge/tests-364%20passing-brightgreen?style=for-the-badge" alt="Tests"/>
</p>

> **Roadmap proyek dibagi 3 Phase.** README teknis lengkap versi sebelumnya diarsipkan di [`README_v12.md`](README_v12.md) dan [`README_v11.md`](README_v11.md).

---

# 📍 Phase 1 — Tim & Tautan

## Tim

| Nama | Role | LinkedIn |
|------|------|----------|
| Chelsea | Data Analyst | [Chelsea](https://linkedin.com/in/chelseaayu) |
| Hilmi | Data Architect | [Hilmi](https://linkedin.com/in/hilmi888/) |
| Monika | UX Researcher | [Monika](https://linkedin.com/in/monika-hermiani) |
| Irpan | Data Engineer | [Irpan](https://linkedin.com/in/irpanpilihanrambe) |

## Tautan

| Resource | Link |
|----------|------|
| Pitch Deck | [Canva](https://www.canva.com/design/DAHETj2ulzg/VIvgxVkQ6I9R24ucphy2mQ/view) |
| Dashboard (Live Demo) | _(menyusul)_ |
| WhatsApp Bot | _(menyusul)_ |
| Video Demo | _(menyusul)_ |

---

# 🚀 Phase 2 — Yang Sudah Kami Bangun (MVP)

## Masalah

Setiap tahun Indonesia kehilangan triliunan rupiah pangan — **40% terjadi di distribusi, bukan produksi**. Di satu kabupaten petani membuang cabai karena harga jatuh; di kabupaten sebelah harga melonjak karena langka. Pemda sering baru tahu krisis **2–3 minggu kemudian**.

## Solusi

**AgriFlow mencocokkan kabupaten surplus dengan kabupaten defisit** — seperti "Uber untuk pangan", tapi paham masa simpan (perishability), jarak jalan nyata, dan **keadilan untuk daerah tertinggal**. Tiga fungsi inti:

- **Deteksi** — temukan anomali harga (lonjakan/anjlok) dari data harga harian.
- **Prediksi** — perkirakan harga 30 hari ke depan.
- **Distribusi** — cocokkan surplus → defisit secara cerdas & adil.

## Arsitektur (High-Level)

```
   SUMBER DATA NYATA                AGRIFLOW ENGINE                  AKSES
  (BPS · PIHPS · OSRM)        ┌──────────────────────────┐
  produksi · konsumsi ──────▶ │ DETEKSI    anomali harga  │ ──┐
  harga · populasi            │ PREDIKSI   forecast 30 hr │   ├──▶ Dashboard peta
  per-kabupaten Jatim         │ DISTRIBUSI matching 4-lapis│  └──▶ WhatsApp bot
                              └──────────────────────────┘
```

Tiga fungsi (Deteksi · Prediksi · Distribusi) berbagi satu sumber data nyata, lalu disajikan lewat Dashboard & WhatsApp.

📄 **Detail metodologi tiap fitur — alasan pemilihan metode, cara kerja, evaluasi, validasi, dan sitasi paper: [Dokumen Arsitektur (PDF)](docs/AgriFlow_Architecture.pdf).**

## Fitur yang sudah berjalan

| Fungsi | Fitur | Status |
|--------|-------|:------:|
| **Distribusi** | Matching engine 4-lapis (hard constraints → multi-objective scoring → equity) berjalan di **data BPS asli per-kabupaten (2022)** | ✅ |
| **Deteksi** | Deteksi anomali harga (deseasonalize + robust statistics) pada harga PIHPS harian **2021–2025** | ✅ |
| **Prediksi** | Forecasting harga 30 hari dengan **TimesFM 2.0** (foundation model time-series) | ✅ |
| **Aksesibilitas** | **Chatbot WhatsApp** (tanya harga & rekomendasi) + **Dashboard** peta interaktif | ✅ |
| **Data nyata** | 5 komoditas real per-kab: beras, cabai merah & rawit, bawang merah & putih + harga 5 tahun | ✅ |

> **Kualitas:** 364 tes otomatis lulus — engine teruji, dapat direproduksi, dan jujur soal keterbatasannya (lihat Phase 3).

### Cuplikan

**Dashboard** — peta Jawa Timur dengan bubble surplus/defisit per kabupaten, daftar *top matches*, plus panel **Forecast & Anomali harga** (ketiga fungsi dalam satu layar):

![Dashboard AgriFlow](assets/dashboard.png)

**WhatsApp Bot** — tanya harga, cari pembeli/pemasok, prediksi & anomali harga lewat chat. Mendukung **Bahasa Indonesia** dan **Bahasa Jawa** (inklusi petani daerah):

| Bahasa Indonesia | Bahasa Jawa |
|:---:|:---:|
| ![WhatsApp Bahasa Indonesia](assets/whatsapp-id.png) | ![WhatsApp Bahasa Jawa](assets/whatsapp-jawa.png) |

## Kenapa tech stack kami RINGKAS (bukan sebanyak proposal awal)?

Proposal awal mencantumkan stack besar (Qdrant, LangChain, Redis, n8n, multi-cloud, dll). Setelah benar-benar membangun, kami **sengaja memangkasnya** — *honest engineering* untuk skala saat ini (38 kabupaten Jawa Timur):

| Rencana awal | Yang kami pakai | Alasan |
|---|---|---|
| Qdrant (vector DB terpisah) | **Supabase pgvector** | Korpus kecil — tak perlu service vektor sendiri |
| LangChain | **Gemini API langsung** | RAG sesederhana ini tak butuh framework berat |
| Redis cache | **In-process cache** | Beban belum menuntut; engine deterministik |
| 5 platform hosting | **2 (HF Spaces + Vercel)** | Lebih sedikit titik gagal, lebih murah |

**Prinsip kami: pakai yang cukup, bukan yang ramai.** Komponen besar baru bernilai saat skala membenarkannya — dan itulah **Phase 3**.

---

# 🌐 Phase 3 — Rencana Lanjutan & Scaling

Komponen di bawah ini **sengaja kami tunda** karena *over-engineering* untuk skala sekarang. Kami kerjakan saat **scaling up**:

| Rencana Phase 3 | Untuk apa |
|---|---|
| **Skala nasional 514 kab** | Dari 38 kab Jatim → seluruh Indonesia (perlu spatial partitioning + precompute jarak) |
| **Exogenous forecasting** (indeks ENSO/iklim, kalender Ramadan) | Akurasi prediksi naik saat ada guncangan iklim & hari raya |
| **Qdrant / Redis / n8n** | Vector scale, caching, orkestrasi terjadwal — saat beban nyata muncul |
| **Sahabat-AI (Bahasa Jawa/Madura) + IVR telepon** | Inklusi petani lansia & pengguna feature-phone |
| **Daging ayam & telur (data real)** | Perlu data produksi broiler & telur-ras per-kab yang lengkap |

## Limitasi (jujur, untuk dinilai apa adanya)

- **Data nyata: 5 komoditas, tahun 2022** — tahun terbaru yang konsisten tersedia per-kabupaten. Daging & telur belum (data produksi belum lengkap).
- **Konsumsi cabai & bawang** memakai rata-rata nasional × populasi (proxy); konsumsi **beras sudah per-kabupaten nyata**.
- **Komoditas sangat perishable (cabai)** butuh `harvest_age` real-time dari lapangan — di dataset demo statis, sebagian match terbatas oleh batas kesegaran.
- **Skala**: sudah siap tingkat provinsi (Jatim); nasional 514 kab perlu optimasi — direncanakan di Phase 3.
- **Prediksi (TimesFM)** masih modul terpisah; integrasi penuh ke dashboard menyusul.

## Scaling up

Peningkatan skala (nasional, multi-komoditas penuh, data real-time) **dilakukan di Phase 3**, setelah MVP Phase 2 tervalidasi di lapangan. Pendekatan kami: **buktikan nilai dulu di skala kecil dengan data nyata, baru perbesar.**

---

## Menjalankan (teknis singkat)

```bash
pip install -r requirements.txt
python examples/run_demo_real.py   # demo matching pada data BPS asli 2022
pytest tests/                      # 364 tes
```

Detail engineering lengkap ada di [`README_v12.md`](README_v12.md).

---

## Lisensi

MIT License — &copy; 2026 Hilmi. Lihat [`LICENSE`](LICENSE).

<p align="center"><em>Deteksi · Prediksi · Distribusi — untuk ketahanan pangan Indonesia.</em></p>
