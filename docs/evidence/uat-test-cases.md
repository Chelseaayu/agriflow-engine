# User Acceptance Testing — AgriFlow

**Status: belum dijalankan.** Dokumen ini adalah instrumen, bukan laporan hasil. Kolom
`Hasil`, `Tanggal`, dan `Penguji` sengaja dibiarkan kosong dan hanya boleh diisi oleh orang
yang benar-benar menjalankan langkahnya.

## Cakupan

Yang diuji adalah tiga permukaan yang dipakai pengguna akhir:

1. **Bot WhatsApp** — kanal utama untuk petani ([`whatsapp_bot/`](../../whatsapp_bot))
2. **Dashboard web** — kanal untuk dinas dan analis ([agriflow-engine.vercel.app](https://agriflow-engine.vercel.app/))
3. **API publik** — untuk integrator ([`/api/v1/*`](../../whatsapp_bot/server.py))

## Peran penguji

| Peran | Siapa | Menguji |
|---|---|---|
| P1 Petani | Petani aktif, pengguna WhatsApp harian, bukan anggota tim | UAT-01 sampai UAT-08 |
| P2 Dinas | Staf dinas pertanian atau TPID, terbiasa membaca data | UAT-09 sampai UAT-15 |
| P3 Integrator | Pengembang di luar tim | UAT-16 sampai UAT-18 |

Penguji tidak boleh anggota tim AgriFlow. Penguji yang sudah pernah melihat produk ini
dicatat sebagai penguji terbias dan hasilnya dipisahkan.

## Definisi lulus

Satu kasus **LULUS** bila seluruh kriteria terpenuhi tanpa bantuan lisan dari moderator.
Bila penguji perlu diberi tahu caranya, statusnya **LULUS DENGAN BANTUAN**, dan itu bukan
lulus. Kasus dengan severity Tinggi yang gagal memblokir rilis.

---

## A. Bot WhatsApp (P1 Petani)

| ID | Skenario | Prasyarat | Langkah | Kriteria lulus | Sev | Hasil | Tanggal | Penguji |
|---|---|---|---|---|---|---|---|---|
| UAT-01 | Cek harga komoditas | Nomor WA penguji terdaftar di sandbox | Kirim "harga cabai rawit di Malang" | Balasan memuat harga dan nama daerah, datang < 30 detik, bahasa Indonesia sehari-hari | Tinggi | | | |
| UAT-02 | Cek harga dengan bahasa daerah | sda | Kirim pertanyaan harga dalam bahasa Jawa | Balasan tetap relevan dan dalam bahasa yang dimengerti penguji | Sedang | | | |
| UAT-03 | Cari pembeli surplus | sda | Kirim "saya punya 2 ton bawang merah di Nganjuk, jual ke mana" | Balasan menyebut daerah tujuan konkret beserta alasannya | Tinggi | | | |
| UAT-04 | Cari penjual (arah sebaliknya) | sda | Kirim "cari bawang merah untuk Surabaya" | Balasan menyebut daerah asal pasokan | Sedang | | | |
| UAT-05 | Prakiraan harga | sda | Kirim "harga cabai minggu depan gimana" | Balasan menyampaikan prakiraan **dan** menyatakan itu perkiraan, bukan kepastian | Tinggi | | | |
| UAT-06 | Komoditas di luar cakupan | sda | Tanyakan komoditas yang tidak didukung, misal "harga durian" | Bot menyatakan komoditas itu belum tercakup, tidak mengarang angka, tidak menanyakan ulang tanpa akhir | Tinggi | | | |
| UAT-07 | Batas kuota gratis | Kuota gratis aktif (2 kueri/hari) | Kirim 3 pertanyaan dalam satu hari | Dua terjawab; yang ketiga ditolak dengan penjelasan yang bisa dimengerti dan cara melanjutkan | Tinggi | | | |
| UAT-08 | Pesan ngawur | sda | Kirim teks acak yang bukan pertanyaan | Bot mengaku tidak paham dan memberi contoh pertanyaan, tidak menjawab asal | Sedang | | | |

## B. Dashboard web (P2 Dinas)

| ID | Skenario | Prasyarat | Langkah | Kriteria lulus | Sev | Hasil | Tanggal | Penguji |
|---|---|---|---|---|---|---|---|---|
| UAT-09 | Daftar akun baru | Email aktif, belum pernah daftar | Buka dashboard, daftar, verifikasi email, masuk | Sampai ke halaman utama tanpa bantuan, < 5 menit | Tinggi | | | |
| UAT-10 | Masuk sebagai tamu | Belum masuk | Pilih akses tamu | Peta tampil dengan data, batasan mode tamu jelas | Sedang | | | |
| UAT-11 | Lupa kata sandi | Akun sudah ada | Jalankan alur lupa kata sandi sampai bisa masuk lagi | Berhasil masuk dengan kata sandi baru tanpa menghubungi tim | Tinggi | | | |
| UAT-12 | Baca peta surplus-defisit | Sudah masuk | Pilih satu komoditas, temukan kabupaten paling defisit | Penguji menyebut kabupaten yang benar dan menjelaskan cara ia tahu | Tinggi | | | |
| UAT-13 | Baca panel prakiraan | Sudah masuk | Buka panel prakiraan satu komoditas | Penguji bisa menyatakan arah harga dan menyadari itu perkiraan berinterval | Tinggi | | | |
| UAT-14 | Baca panel anomali | Sudah masuk | Buka panel anomali | Penguji bisa menyebutkan satu anomali dan tanggalnya | Sedang | | | |
| UAT-15 | Keluar dan masuk lagi | Sudah masuk | Keluar, lalu masuk kembali | Sesi bersih, data kembali tampil | Rendah | | | |

## C. API publik (P3 Integrator)

| ID | Skenario | Prasyarat | Langkah | Kriteria lulus | Sev | Hasil | Tanggal | Penguji |
|---|---|---|---|---|---|---|---|---|
| UAT-16 | Panggil endpoint pertama | Hanya berbekal README | Ambil daftar komoditas lewat `/api/v1/commodities` | Berhasil tanpa bertanya ke tim, < 15 menit | Tinggi | | | |
| UAT-17 | Ambil surplus-defisit | sda | Panggil `/api/v1/surplus-deficit` untuk satu komoditas | Struktur balasan bisa dipahami tanpa penjelasan tambahan | Sedang | | | |
| UAT-18 | Salah parameter | sda | Panggil endpoint dengan parameter keliru | Pesan galat menjelaskan yang salah, dan `request_id` muncul untuk dilaporkan | Sedang | | | |

---

## Cara mencatat hasil

Untuk setiap kasus catat: status (LULUS / LULUS DENGAN BANTUAN / GAGAL), waktu yang
dibutuhkan, kutipan langsung ucapan penguji bila ada yang tersendat, dan `request_id` dari
respons bila terjadi galat. Setiap GAGAL dibuka sebagai issue di repositori ini dengan
tautan balik ke ID kasusnya.

Rekapitulasi diisi setelah sesi berjalan:

| | Jumlah |
|---|---:|
| Kasus dijalankan | |
| LULUS | |
| LULUS DENGAN BANTUAN | |
| GAGAL | |
| Gagal severity Tinggi | |
