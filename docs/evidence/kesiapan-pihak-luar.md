# Bukti Kesiapan Pihak Luar

Kategori 5 dari [lima kategori bukti pendukung](README.md).

## Ringkasan

| Item yang diminta | Status | Bukti |
|---|:---:|---|
| Letter of Intent | ✅ | Surat kesediaan uji coba bertanda tangan, 20 Juli 2026 |
| Kesediaan uji coba | ✅ | Sama seperti di atas: piloting Jawa Timur, dashboard + chatbot WhatsApp |
| Validasi ahli domain | ✅ | Peneliti pascadoktoral BRIN menguji langsung dan memberi umpan balik |
| Bukti akses data | ✅ | [BPS](../../sample_data/bps_real/PROVENANCE.md) · [PIHPS Bapanas](../../sample_data/price_history/SOURCE.md) · OSRM |
| Kesepakatan eksplorasi | ⚠️ Sebagian | Surat menyatakan dirinya "dasar pembahasan lebih lanjut", pembahasannya belum berjalan |
| Surat dukungan institusional | ❌ | Belum |
| Notulensi pembahasan pilot | ❌ | Belum, karena pembahasannya belum berlangsung |

## Surat kesediaan uji coba

**Medina Uli Alba Somala, PhD** — Peneliti Pascadoktoral, **Badan Riset dan Inovasi Nasional
(BRIN)**, KST BJ Habibie, Tangerang Selatan.

| | |
|---|---|
| Tanggal | 20 Juli 2026 |
| Bentuk | Surat Kesediaan Uji Coba, bertanda tangan |
| Wilayah | Jawa Timur |
| Bentuk keterlibatan | Uji coba dashboard dan AI WhatsApp Chatbot |
| Sifat | Dinyatakan sendiri dalam surat sebagai **pernyataan minat awal, bukan perjanjian mengikat** |

Kami mengutip sifat suratnya apa adanya. Surat ini menyatakan minat untuk melakukan piloting
dan menjadi dasar pembahasan lanjutan; ia **bukan** komitmen kerja sama yang mengikat, dan
menyebutnya demikian akan melebih-lebihkan posisinya.

**Berkas suratnya sengaja tidak disertakan di repositori publik ini** karena memuat nomor
telepon pribadi, alamat, dan tanda tangan penandatangan. Menerbitkan data kontak seseorang di
repositori publik bukan hal yang pantas kami lakukan hanya demi kelengkapan lampiran. Salinan
asli tersimpan di tim dan dapat diserahkan langsung kepada panitia bila diminta.

## Validasi ahli domain

Penandatangan surat di atas juga menjadi salah satu dari lima early tester pada 22 Juli 2026.
Ia mencoba dashboard **dan** bot WhatsApp, menuntaskan keempat tugas, dan memberi skor 5, 5, 5
untuk kemudahan pakai, kegunaan informasi, dan kemauan merekomendasikan.

> "inovasi yang sangat bagus dan bermanfaat bagi nusa dan bangsa"

Umpan baliknya yang paling berguna justru bukan pujiannya, melainkan permintaan yang sama
dengan tiga peserta lain: **informasi penjual atau supplier**. Berkas sesinya ada di
[`early-testing/`](early-testing/), rekapnya di
[usability-early-testing.md](usability-early-testing.md).

Perlu disebut jujur: validasi ini datang dari seorang peneliti, bukan dari dinas pertanian,
Bapanas, atau Bulog. Untuk keputusan alokasi pangan yang sesungguhnya, validasi dari pemegang
kewenangan itulah yang akan menentukan, dan kami belum memilikinya.

## Bukti akses data

Seluruh data pangan yang dilayani AgriFlow berasal dari sumber resmi dan **terunut sampai
berkas aslinya**, bukan dari data buatan.

| Sumber | Isi | Provenance |
|---|---|---|
| **BPS dan BPS Jawa Timur** | Produksi, konsumsi, dan populasi 38 kabupaten/kota, 2021 sampai 2025 | [`PROVENANCE.md`](../../sample_data/bps_real/PROVENANCE.md) |
| **PIHPS, Badan Pangan Nasional** | 70.953 baris harga harian, 8 kota IHK × 7 komoditas, 2021-01-04 sampai 2025-12-31 | [`SOURCE.md`](../../sample_data/price_history/SOURCE.md) |
| **Kementan** | Konsumsi per kapita hortikultura | `Statistik_Konsumsi_2024.pdf`, ikut divendorkan |
| **OSRM** | 1.444 jarak jalan antar-kabupaten | [`osrm_distance_matrix.csv`](../../benchmarks/ab_test_road_distance/) |

Kedua berkas provenance mencatat tanggal pengambilan, cakupan baris, satuan asli, dan setiap
transformasi yang kami lakukan, termasuk konversi kuintal ke ton dan normalisasi penamaan
komoditas. Metodologi lengkapnya di
[`REAL_DATA_METHODOLOGY.md`](../../REAL_DATA_METHODOLOGY.md), dan angkanya dikunci
[57 tes validasi data nyata](pengujian.md#1-test-case).

Semua sumber di atas adalah data publik yang diakses secara terbuka. Kami **tidak** mengklaim
punya perjanjian berbagi data istimewa dengan BPS, Bapanas, atau Kementan.

## Yang belum ada

- **Surat dukungan dari dinas atau institusi pemerintah.** Belum ada.
- **Notulensi pembahasan pilot.** Belum ada, karena pembahasannya memang belum berlangsung.
- **Kesepakatan eksplorasi formal.** Yang ada baru pernyataan minat satu pihak.

Gambaran jujurnya: AgriFlow punya **satu** pihak luar yang menyatakan kesediaan menguji dan
sekaligus sudah benar-benar mencobanya, ditambah akses penuh ke data resmi yang dibutuhkan.
Yang belum dimiliki adalah komitmen institusional dari pemegang kewenangan alokasi pangan, dan
itulah pintu berikutnya yang harus dibuka.
