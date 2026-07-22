# Bukti Pengujian AgriFlow

Halaman ini memetakan setiap kategori bukti pengujian ke artefak yang benar-benar ada di
repositori ini. Setiap baris menunjuk file yang bisa dibuka, dan setiap angka bisa
direproduksi dengan satu perintah.

Aturan yang kami pegang: **kalau pengujiannya belum dijalankan, statusnya ditulis belum
dijalankan.** Tidak ada hasil yang dikarang untuk mengisi tabel.

Terakhir dijalankan ulang: **22 Juli 2026** (kecuali yang ditandai lain).

---

## Ringkasan status

| # | Kategori | Status | Bukti |
|---|---|---|---|
| 1 | Test case | ✅ Ada | [523 lulus, 1 skip](runs/pytest.txt) · [`tests/`](../../tests) · [CI](../../.github/workflows/test.yml) |
| 2 | Hasil eksperimen | ✅ Ada | [greedy vs optimal](#2-hasil-eksperimen) · [sensitivitas bobot](runs/weight_sensitivity.txt) · [gap dua detektor](runs/anomaly_detector_gap.txt) |
| 3 | Model evaluation | ✅ Ada | [backtest holdout, MAPE 10,8%](runs/backtest_baseline.txt) |
| 4 | Performance test | ✅ Ada | [latency](runs/latency.txt) · [skala nasional](runs/national_scale.txt) · [beban dashboard](runs/dashboard_load.txt) |
| 5 | A/B test | ✅ Ada | [haversine vs jarak jalan](runs/ab_test_road_distance.txt) |
| 6 | Hasil simulasi | ✅ Ada | [24 skenario edge-case](#6-hasil-simulasi) · [skenario pasokan langka](runs/equity_comparison_constrained.txt) |
| 7 | Validation report | ✅ Ada | [Audit menyeluruh Juli 2026](../AgriFlow_Audit_2026-07.pdf) · [metodologi data nyata](../../REAL_DATA_METHODOLOGY.md) |
| 8 | Security test awal | ✅ Ada | [ringkasan](security-review.md) · 117 tes auth/kuota/RLS |
| 9 | Error log | ✅ Ada | [contoh log JSON](runs/api-request-log-sample.jsonl) · [`whatsapp_bot/request_log.py`](../../whatsapp_bot/request_log.py) |
| 10 | Usability testing | ✅ Putaran 1 selesai | [5 sesi, 20 sampai 22 Juli 2026](usability-early-testing.md) · [protokol putaran 2](usability-test-protocol.md) |
| 11 | UAT | ⏳ Instrumen siap, **belum dijalankan** | [lembar UAT](uat-test-cases.md) |

Baris terakhir sengaja tidak diberi angka. Instrumennya lengkap dan siap pakai, tetapi
menuntut penguji di luar tim, dan sesi itu belum terlaksana.

Usability testing sudah punya hasil nyata: lima sesi berbasis tugas dengan pengguna nyata,
100% tugas tuntas, skor kepuasan rata-rata 4,4 sampai 4,8 dari 5. Sesi itu dimoderasi
anggota tim dan pesertanya baru lima orang, jadi
[keterbatasannya dicantumkan bersama hasilnya](usability-early-testing.md#cara-membaca-hasil-ini).

Terpisah dari itu, ada **4 wawancara petani** dengan rekaman audio
([di README utama](../../README.md#-validasi-lapangan--wawancara-petani)). Wawancara itu
bukti *kebutuhan*, bukan bukti *kemudahan pakai*, dan tidak dihitung sebagai usability
testing.

---

## 1. Test case

```
python -m pytest -q
```

**523 lulus · 1 skip · 24 file** ([keluaran lengkap](runs/pytest.txt)). CI menjalankan
matriks 4 leg (Ubuntu + Windows × Python 3.11 + 3.12) pada setiap push dan pull request.

| File | Tes | File | Tes |
|---|---:|---|---:|
| test_subscription_quota | 74 | test_layer1_constraints | 19 |
| test_price_anomaly | 49 | test_layer0_tier | 16 |
| test_forecast_anomaly_api | 40 | test_constrained_scenario | 15 |
| test_price_ingest | 33 | test_layer3_allocation | 14 |
| test_auth | 29 | test_auth_jwks | 14 |
| test_scenarios_tier1_extensions | 27 | test_scenarios_political | 11 |
| test_layer2_scoring | 24 | test_db_loader | 11 |
| test_baseline_comparison | 24 | test_scenarios_disruption | 9 |
| test_whatsapp_bot | 23 | test_road_distance | 9 |
| test_real_data_pipeline | 23 | test_scenarios_temporal | 7 |
| test_real_surplus_deficit_horti_2022 | 22 | test_scenarios_spatial | 6 |
| test_real_surplus_deficit_beras | 21 | test_scenarios_volume | 4 |

Yang di-skip adalah `test_timesfm_importorskip`: dilewati bila pustaka TimesFM tidak
terpasang di runner. Jalur forecasting tetap diuji lewat fallback dan kontrak API.

**Cacat yang kami ketahui.** `test_auth_jwks.py::test_correct_key_selected_from_multi_key_set`
pernah gagal satu kali pada 22 Juli 2026 dengan `PyJWKClientError: Unable to find a signing
key that matches: "new-kid"`, lalu lulus pada empat kali jalan berikutnya termasuk saat
dijalankan sendirian. Tes itu menyalakan server HTTP JWKS sungguhan di thread terpisah,
jadi dugaan kami ini sensitif terhadap timing. Kami belum menemukan akar masalahnya,
sehingga tidak kami klaim sudah selesai. Angka 523/1 di atas adalah kondisi yang stabil
kami amati.

## 2. Hasil eksperimen

| Eksperimen | Pertanyaan yang dijawab | Artefak |
|---|---|---|
| Greedy vs optimal | Apakah alokasi greedy sudah cukup, atau kalah dari solusi eksak? | [`benchmarks/greedy_vs_optimal.py`](../../benchmarks/greedy_vs_optimal.py) → [JSON 100 trial](../../benchmarks/output/greedy_vs_optimal_2026-07-20.json) |
| Sensitivitas bobot | Apakah kesimpulan bergantung pada lima bobot skor yang kami pilih? | [`benchmarks/weight_sensitivity.py`](../../benchmarks/weight_sensitivity.py) → [hasil](runs/weight_sensitivity.txt) |
| Gap dua detektor anomali | Dua detektor hidup berdampingan di kode. Seberapa jauh bedanya? | [`benchmarks/anomaly_detector_gap.py`](../../benchmarks/anomaly_detector_gap.py) → [hasil](runs/anomaly_detector_gap.txt) |
| Perbandingan baseline | Apakah AgriFlow mengalahkan greedy, uniform, dan proporsional? | [`benchmarks/equity_comparison.py`](../../benchmarks/equity_comparison.py) → [hasil](../../benchmarks/output/equity_comparison.md) |

Tiga temuan yang perlu dibaca apa adanya:

- **Greedy bukan optimal.** Pada n=12, greedy kalah di 100 dari 100 percobaan, dengan gap
  rata-rata 6%. Premis awal kami bahwa greedy sudah cukup ternyata keliru; itu berasal dari
  contoh 3×3 yang kebetulan optimal.
- **Bobot bukan titik rapuh.** Mengguncang kelima bobot ±0,05 menggeser coverage paling
  jauh 0,0124 dan Gini 0,0106, dengan Jaccard alokasi tetap 1,0000. Kesimpulan equity tidak
  bergantung pada penyetelan bobot.
- **Detektor 3σ di jalur alokasi buta mulai kontaminasi 14,7%.** Detektor MAD di jalur
  dashboard menandai lonjakan 3× pada 200/200 percobaan di semua level kontaminasi;
  detektor 3σ yang menggerakkan alokasi turun ke 52/200 saat kontaminasi 46,7%. Ini
  temuan terbuka, bukan fitur.

## 3. Model evaluation

```
python analysis/backtest_baseline.py --json analysis/output/backtest_baseline.json
```

Backtest holdout bebas kebocoran atas peramal yang **benar-benar dilayani produksi**
(seasonal-naive), bukan atas model yang belum terpasang. Holdout 30 hari terakhir, 70 seri,
7 komoditas ([keluaran](runs/backtest_baseline.txt), [JSON](../../analysis/output/backtest_baseline.json)).

| Komoditas | Seri | MAPE% | MAE (Rp) | Cakupan CI80% |
|---|---:|---:|---:|---:|
| beras_premium | 15 | 3,6 | 568 | 67% |
| beras_medium | 15 | 4,8 | 696 | 48% |
| telur_ayam | 8 | 9,1 | 2.688 | 15% |
| daging_ayam | 8 | 10,2 | 3.828 | 5% |
| bawang_putih | 8 | 16,8 | 5.169 | 32% |
| bawang_merah | 8 | 19,4 | 9.769 | 27% |
| cabai_rawit | 8 | 23,2 | 14.305 | 72% |
| **Keseluruhan** | **70** | **10,8** | | **42%** |

**Interval kepercayaannya belum terkalibrasi dan kami tidak menyembunyikannya.** Pita yang
dilabeli 80% hanya mencapai cakupan 42%, karena pita itu mencerminkan sebaran antar-tahun
per bulan, bukan galat ramalan, dan lebarnya tidak bertambah seiring horizon. Perbaikannya
menuntut kuantil residual empiris per komoditas. Angka yang boleh dikutip dari sini adalah
MAPE 10,8%; label "interval 80%" belum boleh diklaim tercapai.

Pipeline TimesFM 2.0 ada di [`analysis/forecast_timesfm.py`](../../analysis/forecast_timesfm.py),
tetapi **56 dari 56 ramalan yang saat ini dilayani berlabel `seasonal_naive_baseline`**.
Selama TimesFM belum benar-benar melayani, angka yang kami kutip adalah angka baseline.

## 4. Performance test

| Uji | Hasil | Artefak |
|---|---|---|
| Latency engine | p99 tertinggi **69,07 ms** terhadap target 500 ms (margin 86,2%) | [hasil](runs/latency.txt) |
| Skala nasional | 514 kab × 19 komoditas: p99 **3.021,9 ms** — **6× di atas target** | [hasil](runs/national_scale.txt) |
| Beban dashboard | 1.000 pengguna, 5.000 permintaan, **1.096 req/s**, p99 208,9 ms, **0 gagal** | [hasil](runs/dashboard_load.txt) |

Skala provinsi (38 kabupaten Jawa Timur) aman dengan margin besar. Skala nasional **belum**
memenuhi target dan itu kami cantumkan apa adanya: butuh spatial indexing, matriks jarak
ter-cache, atau dekomposisi per provinsi sebelum layak dipakai nasional.

CI juga menjalankan benchmark latency pada setiap push ke `main` dan mengunggahnya sebagai
artefak, tetapi retensinya hanya 30 hari. Berkas di folder ini adalah salinan permanennya.

## 5. A/B test

```
python benchmarks/ab_test_road_distance/ab_test.py
```

Arm A memakai jarak garis lurus (haversine), Arm B memakai jarak jalan OSRM. Arm B adalah
perilaku produksi hari ini ([hasil](runs/ab_test_road_distance.txt)).

| Metrik | Arm A (haversine) | Arm B (jarak jalan) | Delta |
|---|---:|---:|---:|
| Total skor tertimbang volume | 126.424,2 | 122.869,5 | −2,81% |
| Volume tercocokkan (ton) | 1.559,0 | 1.540,0 | −1,22% |
| Pasangan yang hanya muncul di satu arm | 1 | 1 | |

Arm B terlihat "lebih buruk" pada kedua metrik, dan justru itu alasannya dipakai. Haversine
memendekkan jarak sampai 36 km pada pasangan nyata (Bangkalan→Gresik 18 km garis lurus
versus 54 km lewat jalan, karena harus memutari Jembatan Suramadu). Jarak semu itu
melahirkan pencocokan yang tidak benar-benar layak dalam radius kesegaran, misalnya
Kota Batu→Bondowoso untuk tomat yang gugur begitu jaraknya dihitung jujur. Selisih −2,81%
adalah optimisme palsu yang kami buang, bukan kinerja yang hilang.

Catatan reproduksi: skrip ini pertama kali dijalankan Mei 2026 ketika haversine masih
menjadi default. Setelah jarak jalan diadopsi, skrip lama melaporkan selisih nol karena
menambal fungsi yang tidak lagi dipanggil di jalur itu. Lengan uji sudah diarahkan ulang ke
`road_distance_km` agar kembali mengukur hal yang diklaimnya.

## 6. Hasil simulasi

**24 skenario edge-case (A–F)** memetakan kejadian nyata Jawa Timur, dijalankan sebagai tes
otomatis di [`tests/test_scenarios_*.py`](../../tests):

| Berkas | Skenario | Contoh |
|---|---:|---|
| [temporal](../../tests/test_scenarios_temporal.py) | 7 | C1 lonjakan Ramadan |
| [disruption](../../tests/test_scenarios_disruption.py) | 9 | D4 erupsi Semeru di Lumajang, D5 banjir multi-kabupaten |
| [political](../../tests/test_scenarios_political.py) | 11 | E3 prioritas kontrak Bulog, E5 kenaikan BBM |
| [spatial](../../tests/test_scenarios_spatial.py) | 6 | pulau terpisah, jarak ekstrem |
| [volume](../../tests/test_scenarios_volume.py) | 4 | surplus/defisit ekstrem |
| [tier-1 extensions](../../tests/test_scenarios_tier1_extensions.py) | 27 | turunan tiap tier |

Simulasi pasokan langka ([hasil](runs/equity_comparison_constrained.txt)): greedy murni
menelantarkan Madura (Sampang 0%, Bangkalan 20%); AgriFlow mengangkat keduanya ke 100%
dengan coverage agregat identik (0,6649) dan Gini turun dari 0,3017 ke 0,2905.

Fixture skenario itu **buatan, bukan data BPS**, dan itu disebut eksplisit: Jawa Timur 2022
justru surplus 6,6×, sehingga nilai equity tidak akan tampak pada data nyata. Kami tidak
mengklaim keunggulan equity saat pasokan melimpah.

### Satu regresi yang ditemukan justru saat menyusun halaman ini

Menjalankan ulang `equity_comparison_constrained.py` pada 22 Juli 2026 mula-mula
menghasilkan angka yang jauh berbeda dari berkas yang sudah ter-commit: coverage AgriFlow
0,2172 alih-alih 0,6649, Sampang kembali 0%, dan AgriFlow menjadi identik dengan greedy.
Bila dibiarkan, klaim equity di README tidak akan bisa direproduksi dari checkout bersih.

Akarnya: sejak commit `2819ca6`, `sample_data/historical_price_stats.csv` berisi median dan
deviasi **PIHPS asli**. Filter 3σ di `run_matching()` membandingkan harga tiap simpul
terhadap statistik itu, sedangkan fixture skenario ini sintetis dan disusun terhadap
statistik sintetis yang lama. Akibatnya filter membuang 7 simpul fixture (contohnya
"Kota Surabaya Beras Premium @ Rp 17.000/kg") sebelum strategi mana pun sempat mengalokasi,
sehingga kelima strategi dibandingkan di atas kolam pasokan yang sudah berubah.

Perbaikannya: skrip benchmark kini menjalankan perbandingan tanpa statistik harga yang tidak
sepadan itu, sama seperti [`tests/test_constrained_scenario.py`](../../tests/test_constrained_scenario.py)
yang mengunci angka yang sama. Setelah itu keluarannya reproduksi persis seperti berkas yang
ter-commit. **Jalur data nyata tidak terdampak**: `load_real_data()` menghasilkan nol
pengecualian anomali, karena di sana harga dan statistiknya berasal dari sumber yang sama.

Ini juga menjelaskan mengapa detektor 3σ di jalur alokasi tetap menjadi temuan terbuka
(lihat bagian eksperimen di atas): ia sensitif terhadap distribusi yang dipakai
mengkalibrasinya.

## 7. Validation report

[**Audit Menyeluruh Juli 2026**](../AgriFlow_Audit_2026-07.pdf) ([sumber TeX](../AgriFlow_Audit_2026-07.tex))
memeriksa test suite, repositori, deployment web, dan setiap klaim menonjol di README
terhadap bukti terukur. Isinya termasuk tabel klaim-versus-bukti, tujuh temuan bernomor
dengan tingkat keparahan, dan bab reproduksi berisi perintah yang bisa dijalankan ulang.

Audit itu memuat temuan yang tidak menguntungkan kami, dan kami menerbitkannya utuh.
Temuan F2 (README mengklaim TimesFM padahal yang dilayani baseline) sudah kami perbaiki di
README menyusul audit ini.

Validasi data nyata: [`REAL_DATA_METHODOLOGY.md`](../../REAL_DATA_METHODOLOGY.md) dan
[`sample_data/bps_real/PROVENANCE.md`](../../sample_data/bps_real/PROVENANCE.md) merunut
setiap angka food-balance ke berkas BPS sumbernya.

## 8. Security test awal

Ringkasan dan cakupannya: [security-review.md](security-review.md). Ini uji keamanan awal
yang dijalankan sendiri oleh tim, **bukan penetration test pihak ketiga**, dan kami tidak
menyebutnya demikian.

## 9. Error log

API menuliskan satu objek JSON per permintaan ke stderr, ditambah header `X-Request-ID`
agar laporan pengguna bisa ditarik ke baris log yang persis
([`whatsapp_bot/request_log.py`](../../whatsapp_bot/request_log.py)).

```
python scripts/capture_error_log.py
```

[Contoh log](runs/api-request-log-sample.jsonl) berisi enam baris: tiga permintaan sehat,
404, 422, dan satu kegagalan server yang sengaja dipicu untuk memperlihatkan bentuk baris
ERROR lengkap dengan tipe pengecualian dan ekor traceback.

Nomor telepon tidak pernah masuk log. Parameter yang berbau identitas atau kredensial
diganti `<redacted>`, dan badan permintaan tidak dicatat sama sekali.

## 10. Usability testing

**Putaran 1 sudah dijalankan**: lima sesi berbasis tugas pada 20 sampai 22 Juli 2026, empat
petani lintas komoditas (cabai, bawang merah, kentang, padi) dan satu peneliti pascadoktoral
BRIN, memakai dashboard dan bot WhatsApp.

| | |
|---|---|
| Tugas tuntas | 20 dari 20 (100%) |
| Kemudahan pakai | 4,6 dari 5 |
| Kegunaan informasi | 4,8 dari 5 |
| Kemauan merekomendasikan | 4,4 dari 5 |
| Permintaan paling berulang | Informasi penjual atau supplier (3 dari 5 peserta) |

Hasil lengkap, kutipan peserta, dan berkas sesi asli beserta screenshot:
[usability-early-testing.md](usability-early-testing.md). Sesi dimoderasi anggota tim dan
pesertanya baru lima orang; keterbatasan itu ditulis bersama hasilnya, bukan di catatan kaki.
[Protokol putaran 2](usability-test-protocol.md) dirancang untuk menutup ketiga
keterbatasan tersebut.

## 11. UAT

[Lembar UAT](uat-test-cases.md) berisi kasus uji dengan langkah, prasyarat, dan kriteria
lulus. **Kolom hasilnya masih kosong karena sesinya belum dijalankan.** Berbeda dari
usability testing di atas, UAT menuntut penguji di luar tim, termasuk seorang integrator
yang mencoba API hanya berbekal README.
