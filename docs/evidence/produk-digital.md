# Bukti Produk Digital

Kategori 1 dari [lima kategori bukti pendukung](README.md).

Status AgriFlow hari ini: **MVP yang berjalan di produksi**, bukan mockup dan bukan
proof of concept. Dashboard, API, dan engine ketiganya hidup dan bisa dicoba panitia
tanpa membuat akun.

## Ringkasan

| Item yang diminta | Status | Bukti |
|---|:---:|---|
| Functional prototype | ✅ | Dashboard + bot WhatsApp + API, ketiganya berjalan |
| MVP | ✅ | Tiga pilar (deteksi, prediksi, distribusi) sudah melayani pengguna |
| Proof of concept | ✅ | [Demo data BPS asli 2022](runs/demo_real_bps.txt) |
| Source code repository | ✅ | Repositori ini, 183 berkas ter-track, lisensi terbuka |
| API test | ✅ | [Respons API produksi live](runs/api-live-responses.md) · 40 tes otomatis endpoint |
| Working dashboard | ✅ | [agriflow-engine.vercel.app](https://agriflow-engine.vercel.app/) |
| Alpha/beta version | ✅ | Versi beta publik, akses tamu tanpa registrasi |
| Demo dengan input dan output nyata | ✅ | [Keluaran demo](runs/demo_real_bps.txt) · [respons API](runs/api-live-responses.md) |
| Model atau rule engine yang dapat dijalankan | ✅ | [`matching_engine/`](../../matching_engine) 4 lapis, satu perintah |

**Kesembilan item terpenuhi.** Satu catatan di luar daftar itu: repositori belum punya rilis
bernomor, masih berjalan di `main` tanpa penandaan versi formal. Itu bukan salah satu item yang
diminta, tetapi kami sebutkan agar gambarannya utuh.

## Coba sendiri dalam tiga menit

```bash
git clone https://github.com/masterA88/agriflow-engine.git
cd agriflow-engine
pip install -r requirements.txt
python examples/run_demo_real.py
```

Keluarannya bekerja di atas **data BPS Jawa Timur 2022 yang asli**, bukan data contoh:
228 baris, 6 komoditas, 38 kabupaten. Salinan keluaran yang kami jalankan pada 22 Juli 2026
ada di [`runs/demo_real_bps.txt`](runs/demo_real_bps.txt).

| Komoditas | Match | Volume tercocokkan |
|---|---:|---:|
| beras_premium | 12 | 222.386,6 ton |
| beras_medium | 12 | 148.257,8 ton |
| bawang_merah | 21 | 51.834,3 ton |
| cabai_merah | 21 | 22.737,5 ton |
| cabai_rawit | 18 | 21.828,7 ton |
| bawang_putih | 0 | — |

Baris terakhir bukan kegagalan. Jawa Timur 2022 defisit bawang putih di seluruh 38 kabupaten
(produksi ~855 ton berbanding konsumsi ~80.640 ton), konsisten dengan posisi Indonesia sebagai
net-importir bawang putih. Engine menanganinya dengan benar: nol match domestik, lalu
mengalihkannya ke jalur `external_opportunity` berupa saran impor. **Datanya yang bicara, bukan
enginenya yang rusak.**

## Dashboard

[agriflow-engine.vercel.app](https://agriflow-engine.vercel.app/) — situs bersifat *login-first*.
Panitia cukup menekan **"Masuk sebagai Tamu"** untuk meninjau tanpa membuat akun.

Isinya: peta Jawa Timur dengan bubble surplus dan defisit per kabupaten, daftar rekomendasi
distribusi terurut prioritas, panel prakiraan harga, dan panel anomali. Screenshot yang diambil
pengguna sungguhan saat sesi pengujian ada di dalam
[berkas sesi early tester](early-testing/), jadi tampilannya terbukti bukan hasil render khusus
untuk juri.

## API produksi

Base URL: `https://masteraaa123-agriflow-api.hf.space`

[`runs/api-live-responses.md`](runs/api-live-responses.md) memuat respons **asli** dari tujuh
pemanggilan yang kami jalankan pada 22 Juli 2026 terhadap API produksi, bukan terhadap salinan
lokal. Semuanya bisa diulang dengan `curl`:

```bash
curl https://masteraaa123-agriflow-api.hf.space/health
curl "https://masteraaa123-agriflow-api.hf.space/api/v1/matches?commodity=bawang_merah&limit=3"
```

| Endpoint | Fungsi | Hasil |
|---|---|:---:|
| `/health` | Liveness dan konfigurasi runtime | 200 |
| `/api/v1/commodities` | Daftar komoditas | 200 |
| `/api/v1/surplus-deficit` | Neraca per kabupaten | 200 |
| `/api/v1/matches` | Rekomendasi distribusi | 200 |
| `/api/v1/forecast` | Prakiraan harga 30 hari | 200 |
| `/api/v1/anomalies` | Anomali harga | 200 |
| `/api/v1/forecast` dengan parameter salah | Uji penanganan galat | 404 dengan pesan yang bisa dipakai memperbaiki diri |

Pemanggilan terakhir sengaja dibuat salah, memakai `city=Kota Surabaya` alih-alih kode IHK
`city=3578`. API membalas 404 sambil **menyebutkan pasangan yang tersedia** sehingga pemanggil
bisa mengoreksi sendiri. Kami cantumkan ini apa adanya: penanganan galatnya benar, tetapi
parameter `city` yang menuntut kode IHK memang belum intuitif, dan itu tercatat sebagai temuan
terbuka di [laporan audit](../AgriFlow_Audit_2026-07.pdf).

### Dua hal yang jujur perlu disebut tentang API produksi

`GET /health` melaporkan `"mock_mode": true` dan `"gemini_mock": true`. Artinya: **data pangan
yang dilayani sepenuhnya nyata** (`"data_loaded": true`, 38 kabupaten, 6 komoditas BPS asli),
tetapi lapisan bahasa alaminya masih memakai balasan tiruan, bukan panggilan Gemini berbayar,
dan kanal WhatsApp berjalan tanpa kredensial Twilio produksi. Kami memilih menjalankan demo
publik tanpa kunci berbayar, dan API-nya melaporkan status itu dengan jujur alih-alih
menyamarkannya.

## Bot WhatsApp

Kode di [`whatsapp_bot/`](../../whatsapp_bot). Enam jenis intent: cek harga, cari pembeli, cari
penjual, prakiraan, anomali, dan fallback. Mendukung Bahasa Indonesia dan Bahasa Jawa.

Bukti percakapan nyata dari sesi pengujian ada di dalam berkas sesi
[Anisa](early-testing/) berupa screenshot chat: tiga pertanyaan berbeda dijawab dengan
rekomendasi konkret lengkap dengan jarak, skor kecocokan, dan tingkat keyakinan.

## Rule engine yang dapat dijalankan

[`matching_engine/`](../../matching_engine) berisi mesin pencocokan 4 lapis:

| Lapis | Isi | Kode |
|---|---|---|
| L0 | Penentuan tier berbasis IPM | [`engine.py`](../../matching_engine/engine.py) |
| L1 | Hard constraint: jarak, masa simpan, volume | [`constraints.py`](../../matching_engine/constraints.py) |
| L2 | Skor multi-objektif 5 bobot | [`scoring.py`](../../matching_engine/scoring.py) |
| L3 | Alokasi dengan penyeimbangan equity | [`allocation.py`](../../matching_engine/allocation.py) |

Enginenya deterministik dan tidak memanggil layanan luar, sehingga hasilnya dapat direproduksi
persis oleh siapa pun. Seluruh perilakunya dikunci [523 tes otomatis](pengujian.md#1-test-case).
