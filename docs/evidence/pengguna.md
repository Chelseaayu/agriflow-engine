# Bukti Pengguna

Kategori 3 dari [lima kategori bukti pendukung](README.md).

Dua rombongan bukti, dan keduanya berbeda sifat. **Wawancara lapangan** (Mei sampai Juli 2026)
dilakukan sebelum ada produk yang bisa dipegang, jadi isinya bukti *kebutuhan*. **Sesi early
tester** (20 sampai 22 Juli 2026) dilakukan dengan produk di tangan pengguna, jadi isinya bukti
*pemakaian*. Kami tidak mencampur keduanya.

## Ringkasan

| Item yang diminta | Status | Bukti |
|---|:---:|---|
| User feedback | ✅ | [5 berkas sesi + screenshot](early-testing/) |
| Interview setelah testing | ✅ | Bagian "kesan & umpan balik" di tiap berkas sesi |
| Early tester | ✅ | [5 penguji, 20 sampai 22 Juli 2026](usability-early-testing.md) |
| Completion rate | ✅ | 5 dari 5 sesi tuntas |
| Task success rate | ✅ | **20 dari 20 tugas (100%)** |
| Satisfaction score awal | ✅ | Kemudahan 4,6 · kegunaan 4,8 · rekomendasi 4,4 dari 5 |
| Testimoni pengguna | ✅ | [5 kutipan langsung](usability-early-testing.md#kutipan) |
| Hasil observasi penggunaan | ⚠️ Sebagian | Observer hadir di tiap sesi, tetapi kolom waktu per tugas dibiarkan kosong |

## Early tester: lima sesi berbasis tugas

Rincian penuh, termasuk skor per orang dan keterbatasan metodenya, ada di
[usability-early-testing.md](usability-early-testing.md).

| Responden | Profil | Kanal | Tanggal | Tugas |
|---|---|---|---|:---:|
| Aji | Cabai, Kalanganyar, 8 bulan | Dashboard + bot WA | 20 Juli | 4/4 |
| Denisa Septalian Alhamda | Bawang merah, Nganjuk, 5 tahun | Dashboard | 21 Juli | 4/4 |
| Labib | Kentang, Dieng, 2 tahun | Dashboard | 21 Juli | 4/4 |
| Anisa | Padi, Tapanuli Selatan, 15 tahun | Dashboard + bot WA | 22 Juli | 4/4 |
| Medina Uli Alba Somala, PhD | Peneliti pascadoktoral, BRIN | Dashboard + bot WA | 22 Juli | 4/4 |

Empat tugas yang sama diberikan ke setiap orang: cek harga komoditasnya di kabupaten sendiri,
cari pembeli untuk surplus, lihat prediksi atau anomali harga, dan temukan informasi yang
dicari di peta dashboard.

**Berkas sesi aslinya disertakan** di [`early-testing/`](early-testing/), lengkap dengan
screenshot yang diambil saat sesi berlangsung, sehingga angkanya bisa diperiksa dan tidak perlu
dipercaya begitu saja.

## Testimoni

> "Sistem bagus dan canggih" — **Aji**, petani cabai, Kalanganyar

> "Inovasi bagus, harga yang dipatok juga masuk akal, meskipun mungkin untuk tahap awal akan
> coba paket pay as you go terlebih dahulu" — **Denisa Septalian Alhamda**, petani bawang
> merah, Nganjuk

> "inovasi bagus dengan harga murah" — **Labib**, petani kentang, Dieng

> "inovasi yang bagus dan mudah digunakan" — **Anisa**, petani padi, Tapanuli Selatan

> "inovasi yang sangat bagus dan bermanfaat bagi nusa dan bangsa" — **Medina Uli Alba Somala,
> PhD**, peneliti pascadoktoral, BRIN

## Umpan balik yang paling penting bukan pujiannya

Skor tinggi mudah didapat pada sesi yang dimoderasi pembuatnya sendiri. Yang lebih berguna
adalah pola yang berulang lintas peserta:

| Temuan | Berapa peserta | Tindak lanjut |
|---|---|---|
| Minta informasi penjual atau supplier | 3 dari 5 | Masuk backlog; konsisten dengan keluhan "tidak ada akses keluar daerah" pada wawancara lapangan |
| Susah membaca prediksi baseline | Aji | Sejalan dengan temuan terukur bahwa [interval kepercayaan peramal belum terkalibrasi](pengujian.md#3-model-evaluation) |
| Tarif berlangganan membingungkan | Anisa | Perlu penjelasan harga yang lebih jelas sebelum penyebaran luas |
| Tampilan di ponsel kurang bagus | Aji | Perbaikan responsif |
| Ingin jual beli langsung di platform | Aji | Di luar cakupan saat ini; AgriFlow mempertemukan, belum memfasilitasi transaksi |

Tiga dari lima peserta meminta hal yang sama, dan permintaan itu **sudah muncul lebih dulu**
pada wawancara petani sebelum produk ada. Konsistensi lintas dua metode dan dua waktu itu
sinyal yang jauh lebih kuat daripada skor 4,8.

## Wawancara lapangan: bukti kebutuhan

Empat petani lintas komoditas dan skala usaha, masing-masing dengan **rekaman audio** sebagai
bukti, ditambah transkrip di repositori. Tabel lengkap beserta tautan audio dan transkrip ada
di [README utama](../../README.md#-validasi-lapangan--wawancara-petani).

| Komoditas | Narasumber | Inti pendapat |
|---|---|---|
| Bawang merah | Denisa Septalian, Nganjuk | Setuju bersyarat; info harga saja "kurang efektif" karena 100% bergantung tengkulak |
| Padi | Petani 15 tahun, lahan ±1 ha | Info harga lintas daerah membantu; ragu soal keamanan transaksi |
| Cabai | Petani baru, Solo/Karanganyar | Sangat tertarik; info FB/WA saat ini meleset Rp5.000 sampai 15.000/kg |
| Kentang | Labib, Dieng | Berguna sebagai pembanding; kunci keberhasilan akurasi data dan sumber yang jelas |

Empat dari empat memilih WhatsApp di atas SMS atau aplikasi baru, dan itulah yang mendasari
keputusan membangun bot WhatsApp lebih dulu daripada aplikasi mobile.

**Wawancara ini bukan usability testing** dan tidak kami hitung sebagai usability testing.
Saat itu belum ada produk yang bisa dicoba.

## Apa yang membatasi bukti ini

Ditulis di sini, bukan disembunyikan di catatan kaki:

- **Seluruh sesi dimoderasi anggota tim AgriFlow.** Kehadiran pembuat produk menaikkan tingkat
  keberhasilan dan menahan kritik. Angka 4 dari 4 sebaiknya dibaca "tugasnya bisa
  diselesaikan", bukan "bisa diselesaikan tanpa bantuan".
- **Lima peserta itu sedikit**, dan segmen paling berisiko, yaitu petani berusia lanjut dengan
  literasi digital rendah, belum terwakili sama sekali.
- **Waktu per tugas tidak dicatat**, padahal kolomnya tersedia di lembar sesi.

[Protokol putaran 2](usability-test-protocol.md) dirancang khusus untuk menutup ketiga hal itu:
moderator dari luar tim, kuota peserta literasi rendah, dan pencatatan waktu wajib.
