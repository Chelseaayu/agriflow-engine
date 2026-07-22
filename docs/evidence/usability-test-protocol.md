# Protokol Usability Testing — AgriFlow

**Status: belum dijalankan.** Ini instrumen. Bagian hasil di bawah kosong dan hanya diisi
setelah sesi nyata dengan pengguna nyata.

Bedanya dengan UAT: [lembar UAT](uat-test-cases.md) menanyakan *apakah fiturnya bekerja*.
Protokol ini menanyakan *apakah orang bisa memakainya tanpa dijelaskan*. Sebuah fitur bisa
lulus UAT dan tetap gagal di sini.

## Kenapa ini terpisah dari wawancara petani yang sudah ada

Kami sudah mewawancarai 4 petani lintas komoditas dengan rekaman audio
([di README](../../README.md#-validasi-lapangan--wawancara-petani)). Wawancara itu
memvalidasi **kebutuhan**: petani buta harga antar-daerah dan tidak punya akses pembeli
luar kota. Wawancara itu tidak menyentuh produknya sama sekali, karena saat itu belum ada
yang bisa dipegang. Karena itu wawancara tersebut bukan usability testing, dan kami tidak
menghitungnya sebagai usability testing.

## Peserta

| Segmen | Jumlah | Kriteria | Kenapa segmen ini |
|---|---:|---|---|
| Petani, literasi digital rendah | 3 | Usia 45+, memakai WhatsApp, tidak terbiasa aplikasi baru | Segmen yang paling mungkin gagal, dan disebut sendiri oleh narasumber cabai |
| Petani, literasi digital menengah | 2 | Usia < 40, terbiasa marketplace | Batas atas realistis |
| Staf dinas / TPID | 3 | Pekerjaannya membaca data pangan | Pengguna dashboard |

Delapan peserta cukup untuk menemukan sebagian besar masalah besar. Tidak seorang pun boleh
berasal dari tim, keluarga tim, atau pernah melihat produk ini sebelumnya.

## Aturan moderasi

Tugas dibacakan, lalu moderator diam. Tidak ada petunjuk, tidak ada "coba tekan yang itu",
tidak ada menyelamatkan peserta yang tersendat. Bila peserta buntu lebih dari 3 menit,
tugas ditandai gagal dan lanjut ke tugas berikutnya. Moderator hanya boleh berkata
"apa yang sedang Bapak/Ibu pikirkan?" untuk memancing peserta berpikir keras.

Peserta diberi tahu bahwa yang diuji adalah produknya, bukan dirinya, dan bahwa berhenti
kapan saja tidak masalah. Rekaman hanya diambil setelah izin lisan direkam lebih dulu.

## Tugas

### Bot WhatsApp

| ID | Tugas yang dibacakan | Yang diamati | Batas waktu |
|---|---|---|---|
| U-01 | "Bapak/Ibu ingin tahu harga cabai rawit hari ini di daerah sendiri. Silakan coba." | Apakah peserta tahu harus mengirim apa tanpa contoh | 3 menit |
| U-02 | "Bapak/Ibu punya 2 ton bawang merah dan ingin tahu ke daerah mana sebaiknya dijual." | Apakah peserta merumuskan pertanyaan yang dimengerti bot | 3 menit |
| U-03 | "Coba cari tahu perkiraan harga minggu depan." | Apakah peserta memahami itu perkiraan, bukan kepastian | 3 menit |
| U-04 | Setelah U-03: "Menurut Bapak/Ibu, angka tadi seberapa bisa dipercaya?" | Apakah ketidakpastian tersampaikan atau justru dianggap harga pasti | — |

### Dashboard

| ID | Tugas yang dibacakan | Yang diamati | Batas waktu |
|---|---|---|---|
| U-05 | "Silakan masuk ke dashboard ini." | Hambatan di alur daftar dan masuk | 5 menit |
| U-06 | "Cari kabupaten yang paling kekurangan beras." | Apakah peta terbaca tanpa legenda dijelaskan | 4 menit |
| U-07 | "Apakah ada harga yang tidak wajar belakangan ini?" | Apakah panel anomali ditemukan sendiri | 4 menit |
| U-08 | "Jelaskan grafik ini ke rekan Bapak/Ibu." | Apakah tafsirnya benar, atau salah baca | 3 menit |

## Metrik

Untuk setiap tugas dicatat:

- **Tuntas mandiri**: ya / tidak
- **Waktu sampai tuntas**
- **Jumlah salah jalan** (langkah yang dibatalkan atau diulang)
- **Kutipan verbatim** saat peserta tersendat atau salah paham
- **Tingkat kesulitan menurut peserta**, 1 sangat mudah sampai 5 sangat sulit

Di akhir sesi: **SUS** (System Usability Scale, 10 pernyataan) dan satu pertanyaan terbuka,
"apa satu hal yang paling mengganggu?".

## Ambang yang kami pakai

| Metrik | Target |
|---|---|
| Tuntas mandiri, bot WhatsApp | ≥ 80% tugas |
| Tuntas mandiri, dashboard | ≥ 70% tugas |
| Skor SUS rata-rata | ≥ 68 (rata-rata industri) |
| Salah tafsir prakiraan sebagai harga pasti | 0 peserta |

Baris terakhir tidak bisa ditawar. Peserta yang memperlakukan prakiraan sebagai kepastian
lalu menjual berdasarkan itu menanggung kerugian nyata, jadi satu kejadian saja sudah
menjadi cacat yang harus diperbaiki sebelum penyebaran lebih luas.

---

## Hasil

*Diisi setelah sesi dijalankan.*

| | |
|---|---|
| Tanggal sesi | |
| Jumlah peserta | |
| Moderator | |
| Tuntas mandiri, bot | |
| Tuntas mandiri, dashboard | |
| SUS rata-rata | |
| Salah tafsir prakiraan | |

### Temuan

*Satu baris per masalah: tugas, berapa peserta terdampak, keparahan, perbaikan yang
diusulkan.*

### Rekaman

*Tautan rekaman, setelah izin peserta diperoleh.*
