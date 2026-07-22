# Security Test Awal — AgriFlow

**Ini uji keamanan awal yang dijalankan sendiri oleh tim.** Bukan penetration test pihak
ketiga, bukan audit keamanan bersertifikat, dan tidak boleh dibaca sebagai keduanya. Yang
dicakup di bawah adalah properti keamanan yang kami kunci sebagai tes otomatis sehingga
regresinya ketahuan di CI.

Terakhir dijalankan: **22 Juli 2026** ([keluaran suite](runs/pytest.txt)).

## Cakupan otomatis

| Area | Berkas | Tes | Yang dikunci |
|---|---|---:|---|
| Verifikasi token | [`tests/test_auth.py`](../../tests/test_auth.py) | 29 | Token valid diterima; tanpa header, tanda tangan dipalsukan, dan token kedaluwarsa ditolak; endpoint terlindungi benar-benar tertutup; salah konfigurasi gagal menutup, bukan membuka |
| Rotasi kunci JWKS | [`tests/test_auth_jwks.py`](../../tests/test_auth_jwks.py) | 14 | Pemilihan kunci digerakkan header `kid` sehingga rotasi kunci Supabase tidak memutus layanan; algoritma yang tidak diizinkan ditolak; kunci di-cache sehingga tidak ada round trip HTTP per permintaan |
| Kuota dan identitas | [`tests/test_subscription_quota.py`](../../tests/test_subscription_quota.py) | 74 | Identitas pengguna, penyimpanan langganan, penegakan kuota gratis, jalur perintah, dan lapisan HTTP-nya |
| Row Level Security | [`db/verify_rls.py`](../../db/verify_rls.py) | — | 12 tabel ada, RLS menyala di semuanya, tidak ada tabel yang FORCE, dan peran `anon` serta `authenticated` tidak bisa membaca tabel sensitif |

`db/verify_rls.py` dijalankan terhadap Postgres yang hidup, bukan terhadap berkas SQL.
Alasannya ada di kepala berkasnya: `db/schema.sql` pernah dianggap benar karena bisa
di-parse, padahal seed-nya melanggar foreign key dan skrip berhenti di tengah, menyisakan 6
dari 12 tabel tanpa RLS sama sekali. Parsing membuktikan sintaks; hanya eksekusi yang
membuktikan perilaku.

## Keputusan desain yang berdampak keamanan

- **Nomor telepon di-hash, tidak disimpan mentah.** Hash memakai salt dari
  `PHONE_HASH_SALT`.
- **Log tidak pernah memuat nomor telepon.** Parameter beridentitas atau kredensial diganti
  `<redacted>` dan badan permintaan tidak dicatat
  ([`whatsapp_bot/request_log.py`](../../whatsapp_bot/request_log.py)).
- **CORS dibatasi** ke localhost pengembangan plus pola `*.vercel.app` dan `*.hf.space`,
  bukan `*`.
- **Kunci anon Supabase dianggap publik.** Kunci itu memang dikirim ke setiap peramban,
  jadi pertahanan yang sebenarnya adalah RLS, dan itulah yang diverifikasi.

## Yang belum dilakukan

Bagian ini sengaja ada supaya cakupannya tidak terbaca lebih luas dari kenyataan.

- Belum ada penetration test pihak ketiga.
- Belum ada uji beban adversarial atau pengujian rate limit di bawah penyalahgunaan.
- Belum ada pemindaian dependensi terjadwal (Dependabot atau setara) di CI.
- Belum ada uji keamanan pada alur pembayaran, karena pembayarannya masih simulasi.
- `PHONE_HASH_SALT` memunculkan `RuntimeWarning` bila tidak diset, dan peringatan itu
  muncul di suite lokal. Di lingkungan produksi variabel ini **wajib** diisi; tanpa salt,
  hash nomor bisa dibalik dengan brute force atas ruang nomor seluler Indonesia.

## Cara menjalankan ulang

```bash
# Seluruh tes keamanan otomatis
python -m pytest tests/test_auth.py tests/test_auth_jwks.py tests/test_subscription_quota.py -q

# Verifikasi RLS terhadap database hidup
python db/verify_rls.py --db-url postgresql://...
```
