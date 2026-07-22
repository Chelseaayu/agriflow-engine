# Hasil Usability Testing — Putaran 1 (Early Tester)

Lima sesi berbasis tugas dengan pengguna nyata, dijalankan **20 sampai 22 Juli 2026**.
Setiap sesi didampingi observer, memakai empat tugas yang sama, dan ditutup dengan skor
kepuasan serta kutipan langsung.

Berkas sumber tiap sesi ada di [`early-testing/`](early-testing/), lengkap dengan lampiran
screenshot yang diambil saat sesi berlangsung.

## Peserta dan hasil tugas

| Responden | Profil | Kanal | Observer | Tanggal | Tugas berhasil |
|---|---|---|---|---|:---:|
| Aji | Cabai, Kalanganyar, 8 bulan, skala kabupaten | Dashboard + bot WA | Monika | 20 Juli | 4 dari 4 |
| Denisa Septalian Alhamda | Bawang merah, Nganjuk, 5 tahun, skala kabupaten | Dashboard | Chelsea | 21 Juli | 4 dari 4 |
| Labib | Kentang, Dieng, 2 tahun, skala kabupaten | Dashboard | Hilmi | 21 Juli | 4 dari 4 |
| Anisa | Padi, Tapanuli Selatan, 15 tahun, skala kabupaten | Dashboard + bot WA | Irpan | 22 Juli | 4 dari 4 |
| Medina Uli Alba Somala, PhD | Peneliti pascadoktoral, BRIN | Dashboard + bot WA | Hilmi | 22 Juli | 4 dari 4 |

Keempat tugas yang diberikan: cek harga satu komoditas di kabupaten sendiri; cari pembeli
untuk surplus; lihat prediksi atau anomali harga; temukan informasi yang dicari di dashboard
peta.

**Task success rate: 20 dari 20 tugas (100%).**

## Skor kepuasan (skala 1 sampai 5)

| Responden | Kemudahan pakai | Kegunaan informasi | Kemauan merekomendasikan |
|---|:---:|:---:|:---:|
| Aji | 5 | 5 | 5 |
| Denisa | 5 | 5 | 4 |
| Labib | 4 | 5 | 4 |
| Anisa | 4 | 4 | 4 |
| Medina Uli Alba | 5 | 5 | 5 |
| **Rata-rata** | **4,6** | **4,8** | **4,4** |

## Yang paling berguna menurut peserta

| Jawaban | Peserta |
|---|---|
| Rekomendasi distribusi | 3 (Denisa, Labib, Medina) |
| Prediksi harga | 1 (Aji) |
| Data real-time antar daerah | 1 (Anisa) |

## Yang membingungkan atau sulit

| Keluhan | Peserta |
|---|---|
| Membaca prediksi baseline | Aji |
| Tarif berlangganan | Anisa |
| Tidak ada | Denisa, Labib, Medina |

## Fitur yang diminta tapi belum ada

| Permintaan | Peserta |
|---|---|
| Informasi penjual atau supplier | 3 (Denisa, Labib, Medina) |
| Jual beli langsung di dalam platform | Aji |
| Tampilan di ponsel diperbaiki | Aji |

## Kutipan

> "Sistem bagus dan canggih" — Aji, petani cabai

> "Inovasi bagus, harga yang dipatok juga masuk akal, meskipun mungkin untuk tahap awal
> akan coba paket pay as you go terlebih dahulu" — Denisa, petani bawang merah

> "inovasi bagus dengan harga murah" — Labib, petani kentang

> "inovasi yang bagus dan mudah digunakan" — Anisa, petani padi

> "inovasi yang sangat bagus dan bermanfaat bagi nusa dan bangsa" — Medina Uli Alba
> Somala, PhD, peneliti pascadoktoral

## Cara membaca hasil ini

Angka 100% task success dan skor rata-rata di atas 4,4 memang tinggi, dan ada tiga hal yang
membatasi seberapa jauh angka itu boleh dibawa.

**Sesi dimoderasi anggota tim.** Observer pada kelima sesi adalah anggota tim AgriFlow
sendiri. Kehadiran pembuat produk cenderung menaikkan tingkat keberhasilan dan menahan
kritik, dan lembar sesi tidak mencatat apakah peserta sempat dibantu secara lisan. Karena
itu angka 4 dari 4 sebaiknya dibaca sebagai "tugasnya bisa diselesaikan", bukan sebagai
"tugasnya bisa diselesaikan tanpa bantuan".

**Lima peserta itu sedikit, dan komposisinya tidak seimbang.** Empat petani dan satu
peneliti. Segmen yang paling berisiko gagal, yaitu petani berusia lanjut dengan literasi
digital rendah yang justru disebut sendiri oleh narasumber cabai pada wawancara sebelumnya,
belum terwakili sama sekali.

**Skala kepuasan diisi, waktu pengerjaan tidak.** Lembar sesi menyediakan kolom waktu atau
catatan per tugas, tetapi kolom itu dibiarkan kosong, sehingga tidak ada bukti berapa lama
tiap tugas sebenarnya memakan waktu.

Sinyal yang paling bisa dipercaya dari putaran ini justru bukan skornya, melainkan pola
permintaan yang berulang: **tiga dari lima peserta meminta informasi penjual atau supplier**,
dan itu konsisten dengan keluhan pada wawancara lapangan sebelumnya bahwa petani tidak punya
akses ke pembeli luar daerah. Satu keluhan lain layak ditindaklanjuti langsung: Aji kesulitan
membaca prediksi baseline, yang sejalan dengan temuan bahwa
[interval kepercayaan peramal memang belum terkalibrasi](README.md#3-model-evaluation).

[Protokol usability testing](usability-test-protocol.md) dirancang untuk menutup ketiga
keterbatasan itu pada putaran berikutnya: moderator yang tidak boleh menolong, peserta dari
segmen literasi digital rendah, dan pencatatan waktu per tugas.

## Surat kesediaan uji coba

Satu peserta, **Medina Uli Alba Somala, PhD (Peneliti Pascadoktoral, Badan Riset dan Inovasi
Nasional)**, menandatangani surat kesediaan uji coba tertanggal 20 Juli 2026 untuk piloting
AgriFlow di wilayah Jawa Timur, dengan bentuk keterlibatan uji coba dashboard dan chatbot
WhatsApp. Surat itu menyatakan dirinya sebagai pernyataan minat awal, bukan perjanjian
mengikat.

Berkas suratnya **tidak disertakan di repositori ini** karena memuat nomor telepon, alamat,
dan tanda tangan pribadi yang tidak layak dipublikasikan. Salinannya disimpan tim dan dapat
diberikan langsung kepada panitia bila diminta.
