# Panduan Deploy Backend v1.1

Dokumen ini bukan langkah otomatis. Backend v1.1 sudah dikodekan, diuji (544 tes lulus, 8
di-skip), dan dikomit di branch `feat/backend-hackathon`, tetapi **belum di-deploy**. Ini
langkah manual yang perlu Hilmi lakukan sendiri, karena keputusan merge ke `main` dan tag
rilis bukan sesuatu yang dijalankan atas nama pengguna tanpa persetujuan eksplisit.

Website: [master-hilmi.vercel.app](https://master-hilmi.vercel.app/)

---

## 1. Dashboard (Vercel)

Dashboard di-deploy dari `dashboard/` sebagai proyek Vercel terpisah.

- **Kalau proyek Vercel-nya melacak branch `feat/backend-hackathon` langsung**: push ke
  branch ini otomatis memicu preview deploy. Cek preview URL di dashboard Vercel atau di
  komentar PR (kalau PR dibuat). Promosikan ke production lewat `vercel --prod` atau lewat
  UI Vercel setelah preview dikonfirmasi benar.
- **Kalau proyek Vercel-nya melacak `main` saja** (kemungkinan besar, karena deploy
  production `agriflow-engine.vercel.app` biasanya dari `main`): dashboard baru **tidak**
  akan live sampai `feat/backend-hackathon` di-merge ke `main`. Merge itu keputusan Hilmi,
  bukan sesuatu yang dilakukan otomatis di sini.
- Setelah live, verifikasi env var `NEXT_PUBLIC_API_URL` di Vercel project settings
  mengarah ke Space yang sudah menjalankan kode v1.1 (lihat bagian 2), bukan ke Space lama.

## 2. API (Hugging Face Space)

Space produksi saat ini (`masteraaa123-agriflow-api.hf.space`) masih menjalankan kode versi
sebelum v1.1. Ada dua cara mendorong kode v1.1 ke sana:

### Opsi A: push manual ke remote git Space

```bash
git remote add space https://huggingface.co/spaces/masteraaa123/agriflow-api
git push space feat/backend-hackathon:main
```

Cara ini langsung, tapi menuntut kredensial HF (token dengan akses write) tersimpan di
git credential helper atau diketik interaktif saat push.

### Opsi B: lewat GitHub Actions (`deploy-space.yml`), dipicu tag `v1.1.0`

Workflow ini sudah ada di `.github/workflows/deploy-space.yml` dan berjalan otomatis saat
tag `v*` di-push, tapi butuh dua repository setting di GitHub dulu:

1. Repository secret `HF_TOKEN`: token Hugging Face dengan akses write ke Space.
2. Repository variable `HF_SPACE`: nilai `masteraaa123/agriflow-api`.

Tanpa keduanya job deploy melewati dirinya sendiri (job test tetap jalan), jadi tagging
tidak pernah membuat CI merah, tapi juga tidak akan pernah deploy.

Setelah kedua setting itu ada, buat dan push tag rilis:

```bash
git tag v1.1.0
git push origin v1.1.0
```

Workflow menjalankan `pytest -q` dulu, baru meng-upload folder repo ke Space (mengecualikan
`.venv/`, `dashboard/node_modules/`, `dashboard/.next/`, `docs/`, `interview/`, `poster/`,
`assets/`, `*.docx`, `*.pdf`).

## 3. Environment variable yang perlu di-set di Space

Set di Space Settings → Variables and secrets:

| Var | Nilai | Wajib |
|---|---|---|
| `ALLOCATOR` | `lp` | Disarankan (ini juga default di kode, tapi eksplisit lebih aman) |
| `ANOMALY_GATE_WINDOW_DAYS` | `14` | Disarankan (juga default) |
| `AGRIFLOW_COMMIT` | SHA commit yang di-deploy | Disarankan, agar `/health` melaporkan commit yang benar |
| `PHONE_HASH_SALT` | string acak, disimpan sebagai secret | **Wajib sebelum menerima pengguna nyata** (tanpa ini nomor telepon di-hash tanpa salt dan bisa dibalik lewat brute force keyspace HP Indonesia) |
| `MOCK_MODE` | `false` | Hanya kalau kanal live diaktifkan (lihat baris di bawah) |
| `GEMINI_API_KEY` | key asli | Hanya kalau `MOCK_MODE=false` |
| `GEMINI_MODEL` | `gemini-2.5-flash-lite` | Hanya kalau `MOCK_MODE=false` |
| Twilio (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, nomor sandbox/produksi) | kredensial Twilio | Hanya kalau kanal WhatsApp live diaktifkan |

Kalau Space tetap di mode demo publik (seperti sekarang), biarkan `MOCK_MODE=true` dan
lewati baris Gemini/Twilio. `ALLOCATOR`, `ANOMALY_GATE_WINDOW_DAYS`, dan `PHONE_HASH_SALT`
tetap disarankan diset terlepas dari mode mock.

## 4. Smoke check setelah deploy

Jalankan urutan ini setelah Space selesai rebuild (biasanya 1 sampai 3 menit):

```bash
curl -s https://masteraaa123-agriflow-api.hf.space/health | python3 -m json.tool
# Cek: "engine_version": "1.1.0", "allocator": "lp"

curl -s https://masteraaa123-agriflow-api.hf.space/api/v1/meta | python3 -m json.tool
# Endpoint ini sendiri harus 200, bukan 404 (tandanya kode v1.1 sudah live)

curl -s -X POST https://masteraaa123-agriflow-api.hf.space/api/v1/simulate \
  -H 'Content-Type: application/json' \
  -d '{"preset": "semeru"}' | python3 -m json.tool
# Harus 200 dengan hasil simulasi, bukan 404/422
```

Lalu buka dashboard live dan cek tab Beranda: kartu "Data per" harus menampilkan tanggal
data nyata (bukan placeholder atau kosong), tandanya `NEXT_PUBLIC_API_URL` sudah mengarah
ke Space yang benar dan `/api/v1/meta` terpanggil sukses dari client.

## 5. Ringkasan urutan

1. Redeploy API ke Space (opsi A atau B di atas), dengan env var di bagian 3 terset.
2. Jalankan smoke check di bagian 4. Kalau `/health` masih melaporkan versi lama, tunggu
   rebuild Space selesai (cek log build di HF) sebelum melangkah lebih jauh.
3. Pastikan `NEXT_PUBLIC_API_URL` di Vercel menunjuk ke Space yang baru saja diverifikasi.
4. Merge `feat/backend-hackathon` ke `main` kalau dashboard Vercel melacak `main` (keputusan
   Hilmi), lalu redeploy/promote dashboard di Vercel.
5. Verifikasi ulang smoke check dari poin 4, kali ini lewat URL dashboard production, bukan
   API langsung.
