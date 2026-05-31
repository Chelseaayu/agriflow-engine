# AgriFlow — Panduan Lengkap Download Data Real (per-kabupaten Jatim)

> Tujuan: melengkapi data REAL agar engine jalan dengan angka yang bisa dipertanggungjawabkan ke juri BI.
> Metode: **download manual via browser** (Cloudflare BPS meloloskan manusia; otomasi curl/cloudscraper GAGAL).
> Pola ini sama dengan cara data **beras** sudah berhasil didapat.

---

## 1. Status data (per 2026-05-31)

| Input engine | Status | Sumber |
|---|---|---|
| Harga harian (8 kota IHK + nasional, semua komoditas) | ✅ ADA | PIHPS (repo Chelsea) + folder "Harga Komoditas" |
| Populasi per-kab per-tahun | ✅ ADA | BPS Jatim (year_populasi_jatim.csv) |
| IPM, koordinat per-kab | ✅ ADA | BPS (sudah di repo) |
| **Produksi beras** per-kab + **konsumsi beras** per-kab | ✅ ADA & DIOLAH | BPS Jatim + Susenas |
| **Produksi cabai** (besar/rawit/keriting) per-kab | ❌ PERLU | BPS Jatim — Hortikultura |
| **Produksi bawang merah & putih** per-kab | ❌ PERLU | BPS Jatim — Hortikultura |
| **Produksi daging ayam** per-kab | ❌ PERLU | BPS Jatim — Peternakan |
| **Produksi telur ayam** per-kab | ❌ PERLU | BPS Jatim — Peternakan |
| Konsumsi per-kapita (cabai/bawang/daging/telur) | ⚠️ OPSIONAL | Susenas per-kab kalau ada; kalau tidak → pakai angka nasional Kementan × populasi (proxy jujur) |

**Prioritas:** sisi **PRODUKSI per-kab adalah yang wajib** (penggerak surplus). Konsumsi per-kab adalah bonus — kalau tak ada per-kab, kita pakai per-kapita nasional × populasi (sudah punya), ditandai sebagai estimasi.

---

## 2. Yang perlu di-download (checklist)

Semua dari **https://jatim.bps.go.id** → kotak **Pencarian** → buka tabel → tombol **Unduh** (CSV/Excel). **Pilih tahun 2024** (konsisten dengan beras; populasi 2025 di sumber corrupt).

### A. PRODUKSI hortikultura (cabai & bawang) — WAJIB
Cari salah satu judul mirip ini (per-kab):
- [ ] **"Produksi Tanaman Sayuran ... Cabai Besar, Cabai Rawit, Cabai Keriting ... Menurut Kabupaten/Kota"** → simpan `cabai_produksi_2024.csv`
- [ ] **"Produksi Tanaman Sayuran ... Bawang Merah ... Menurut Kabupaten/Kota"** → `bawang_merah_produksi_2024.csv`
- [ ] **"Produksi Tanaman Sayuran ... Bawang Putih ... Menurut Kabupaten/Kota"** → `bawang_putih_produksi_2024.csv`
  - (Cabai besar + keriting → dijumlah jadi `cabai_merah`; cabai rawit → `cabai_rawit`.)
  - **Satuan biasanya KUINTAL** — biarkan apa adanya, DEA konversi ÷10 = ton (catat satuannya di nama/catatan).

### B. PRODUKSI peternakan (daging & telur ayam) — WAJIB
- [ ] **"Produksi Daging Ayam (Ras/Buras) Menurut Kabupaten/Kota"** → `daging_ayam_produksi_2024.csv`
- [ ] **"Produksi Telur Ayam (Ras) Menurut Kabupaten/Kota"** → `telur_ayam_produksi_2024.csv`
  - Satuan biasanya **ton** atau **kg** — catat.

### C. KONSUMSI per-kapita per-kab (opsional, kalau ada)
Cari (BPS, Susenas — sama keluarga dengan data konsumsi beras yang sudah ada):
- [ ] **"Rata-rata Konsumsi Perkapita Seminggu Menurut Kelompok Bumbu-bumbuan Per Kabupaten/Kota"** (untuk cabai & bawang) → `konsumsi_bumbu_perkapita.csv`
- [ ] **"Rata-rata Konsumsi Perkapita Seminggu Menurut Kelompok Daging / Telur Per Kabupaten/Kota"** → `konsumsi_daging_telur_perkapita.csv`
  - Kalau hanya tersedia per kelompok (bukan per komoditas) atau hanya nasional → **lewati**; kita pakai angka nasional Kementan sebagai proxy (didokumentasikan).

### D. SUDAH ADA — JANGAN download ulang
- Populasi per-kab, harga (semua komoditas), IPM, koordinat, beras (produksi+konsumsi).

---

## 3. Cara download (langkah, sama seperti beras)

1. Buka **https://jatim.bps.go.id** di Chrome.
2. Ketik judul (atau kata kunci, mis. `produksi cabai kabupaten`) di **Pencarian** → Enter.
3. Buka tabel yang judulnya **"... Menurut Kabupaten/Kota"** (pastikan per-kab, bukan total provinsi).
4. Pilih **tahun 2024** kalau ada filter tahun.
5. Klik **Unduh** → pilih **CSV** (atau Excel) → simpan ke folder:
   `D:\Research\Project Data\Hackathon\AgriFlow_v9_Engine\sample_data\bps_real\`
6. Beri nama sesuai checklist di atas.

---

## 4. Format target (biar DEA bisa parse seragam)

Idealnya tiap file produksi punya kolom seperti data beras:
```
tahun, kabupaten, produksi        # produksi dalam satuan asli (catat: kuintal/ton/kg)
```
Konsumsi (kalau ada):
```
kabupaten/kota, avg_konsumsi_perkapita_kg, tahun   # kg per kapita per minggu
```
Kalau format BPS beda (mis. kolom per-tahun melebar), **tidak apa-apa** — kirim apa adanya, DEA yang rapikan. Yang penting: **per-kabupaten + ada angka produksi**.

---

## 5. Setelah download

Taruh semua file di `sample_data/bps_real/`, lalu **beri tahu Claude nama file-nya**. DEA akan:
1. Map nama kabupaten → kab_id, konversi satuan (kuintal→ton).
2. Hitung `surplus_deficit = produksi − konsumsi(×populasi)` per kab per komoditas.
3. Extend `sample_data/surplus_deficit_real.csv` (saat ini beras saja) dengan komoditas baru.
4. Update `REAL_DATA_METHODOLOGY.md` dengan sumber + asumsi.

---

## 6. Rumus & konversi (referensi)

- Hortikultura: **kuintal ÷ 10 = ton**.
- Padi GKG → beras giling: **× 0.6286** (sudah dihandle untuk beras).
- Konsumsi tahunan per kab (ton) = `perkapita_kg_per_minggu × 52 × populasi / 1000`.
- `surplus_deficit_ton = produksi_ton − konsumsi_ton` → SURPLUS (>0) / DEFICIT (<0).

---

## 7. Catatan jujur (untuk metodologi pitch)

- Tahun acuan = **2024** (lengkap & konsisten; populasi 2025 di sumber corrupt 1000×).
- Konsumsi per-kab (beras) = survei BPS nyata — bukan asumsi nasional. Untuk komoditas tanpa konsumsi per-kab, pakai per-kapita nasional Kementan × populasi (proxy, ditandai).
- Grade beras (premium/medium) di-split 60/40 (asumsi — bisa diperbaiki dengan rasio harga grade kalau perlu).
