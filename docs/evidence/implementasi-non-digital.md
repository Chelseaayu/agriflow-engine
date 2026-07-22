# Bukti Implementasi Awal Non-Digital

Kategori 4 dari [lima kategori bukti pendukung](README.md).

**Ini kategori paling tipis kami, dan kami tidak berpura-pura sebaliknya.** AgriFlow lahir
sebagai produk digital yang langsung diuji lewat kanal digital, sehingga jejak non-digitalnya
terbatas pada demonstrasi metode kepada pengguna. Menyebut hal lain sebagai "pilot"
akan melebih-lebihkan apa yang benar-benar terjadi.

## Ringkasan

**Satu dari sembilan item terpenuhi, dua lagi hanya sebagian.** Itu angka yang jujur, dan
kami tidak membaguskannya dengan memasukkan bukti dari kategori lain ke sini.

| Item yang diminta | Status | Keterangan |
|---|:---:|---|
| Demonstrasi metode | ✅ | 5 sesi demonstrasi langsung ke pengguna, didampingi observer |
| Simulasi proses | ⚠️ Sebagian | 24 skenario simulasi ada, tetapi dijalankan sebagai kode, bukan role-play manusia |
| Prototype layanan publik | ⚠️ Sebagian | Dashboard dapat diakses publik, tetapi bentuknya digital |
| Pilot layanan | ❌ | Belum. Surat kesediaan uji coba sudah ada, pelaksanaannya belum |
| Role-play | ❌ | Belum |
| Kelas atau modul terbatas | ❌ | Belum |
| Policy sandbox | ❌ | Belum ada pembahasan formal dengan regulator |
| Uji SOP | ❌ | SOP operasional belum disusun |
| Kegiatan komunitas terbatas | ❌ | Belum |

Observasi lapangan lewat 4 wawancara petani beraudio juga kami lakukan, tetapi itu kami hitung
di [kategori pengguna](pengguna.md), bukan di sini, agar tidak dihitung dua kali.

## Yang benar-benar terjadi

### Demonstrasi metode ke pengguna, 20 sampai 22 Juli 2026

Lima sesi tatap muka atau terpandu, masing-masing didampingi observer dari tim, di mana
peserta diberi empat tugas nyata dan diminta mengerjakannya sendiri. Ini demonstrasi metode
AgriFlow ke calon pengguna, bukan presentasi satu arah: yang memegang kendali adalah pesertanya.

Peserta mencakup empat petani lintas komoditas (cabai di Kalanganyar, bawang merah di Nganjuk,
kentang di Dieng, padi di Tapanuli Selatan) dan satu peneliti pascadoktoral BRIN. Berkas
sesinya, termasuk screenshot yang diambil saat itu, ada di
[`early-testing/`](early-testing/), dan rekapnya di
[usability-early-testing.md](usability-early-testing.md).

### Observasi lapangan, Mei sampai Juli 2026

Empat wawancara dengan petani di lokasi masing-masing, setiap wawancara disertai **rekaman
audio** sebagai bukti, dengan transkrip tersimpan di [`interview/`](../../interview). Yang
digali bukan pendapat tentang AgriFlow, melainkan cara kerja mereka sehari-hari: kepada siapa
menjual, bagaimana mengetahui harga, apa yang membuat harga jatuh.

Temuan lapangannya konsisten lintas empat komoditas: harga tidak stabil, panen raya serentak
menjatuhkan harga, dan tidak ada akses informasi harga antar-daerah. Itulah yang kemudian
dijawab tiga pilar AgriFlow.

## Yang belum ada, dan apa yang menghalanginya

**Pilot layanan.** Sudah ada [satu surat kesediaan uji coba bertanda
tangan](kesiapan-pihak-luar.md) untuk piloting di Jawa Timur, tetapi pelaksanaannya belum
berjalan. Pilot yang bermakna menuntut kesediaan pihak yang memegang pasokan nyata, bukan
sekadar pengguna informasi.

**Uji SOP dan policy sandbox.** Keduanya baru masuk akal setelah ada mitra institusional yang
menjalankan alokasi berdasarkan keluaran AgriFlow. Selama keluarannya masih bersifat saran
kepada pengguna perorangan, tidak ada SOP yang bisa diuji dan tidak ada kebijakan yang perlu
di-sandbox.

**Kelas, modul, dan kegiatan komunitas.** Belum kami lakukan. Wawancara menunjukkan hambatan
adopsi terbesar bukan pemahaman konsep, melainkan kepercayaan pada keamanan transaksi, dan itu
tidak diselesaikan oleh pelatihan.

## Catatan tentang "simulasi proses"

AgriFlow punya **24 skenario simulasi** yang memetakan kejadian nyata Jawa Timur: lonjakan
Ramadan, erupsi Semeru di Lumajang, banjir multi-kabupaten di sentra padi, kenaikan BBM,
prioritas kontrak Bulog. Rinciannya di [halaman pengujian](pengujian.md#6-hasil-simulasi).

Kami mencantumkannya di sini dengan tanda peringatan karena simulasi itu **dijalankan sebagai
kode**, bukan sebagai role-play atau gladi bersih dengan manusia. Nilainya nyata untuk
menunjukkan bahwa sistemnya tahan menghadapi skenario ekstrem, tetapi itu bukan implementasi
non-digital, dan kami tidak mengklaimnya demikian.
