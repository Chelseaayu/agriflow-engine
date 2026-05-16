# Deploy AgriFlow — Render version (alternative ke HF Spaces)

Panduan alternatif kalau kamu mau **coba Render lagi** (misal dengan kartu lain — virtual card dari Wise/Jenius/Revolut biasanya lolos kalau kartu utama ditolak).

> **Pilih salah satu jalur saja — jangan deploy di Render DAN HF Spaces bersamaan**, nanti Vercel bingung mau pakai yang mana. Kalau kamu sudah ikut [`DEPLOY.md`](DEPLOY.md) (HF Spaces) dan sekarang mau pindah ke Render, hapus dulu HF Space-nya supaya tidak boros free-tier hour-mu.

Total waktu: ~15 menit.

## Arsitektur

```
┌────────────────┐      HTTPS         ┌──────────────────────┐
│  Vercel        │ ─────────────────→ │  Render              │
│  Next.js       │                    │  FastAPI             │
│  dashboard     │ ←─── JSON ──────── │  (engine + WA bot)   │
└────────────────┘                    └──────────────────────┘
       ▲                                       ▲
       │                                       │ POST /whatsapp
   judges /                                    │
   teammates                              ┌────┴─────┐
                                          │ Twilio   │
                                          │ Sandbox  │
                                          └──────────┘
```

- **Vercel free**: Next.js dashboard. Unlimited bandwidth di hobby tier. Card opsional.
- **Render free**: FastAPI server. 750 instance-hour/bulan. **Butuh kartu untuk verifikasi identitas** (bukan untuk billing — free tier tetap gratis). Sleep setelah ~15 menit idle → cold start ~30 detik.
- **Twilio Sandbox**: sama, tinggal arahkan webhook ke URL Render.

---

## Pra-syarat: aktifkan kembali `render.yaml`

Setelah pivot ke HF Spaces, `render.yaml` aku ubah jadi `render.yaml.disabled`. Sebelum mulai, kembalikan dulu:

```bash
git mv render.yaml.disabled render.yaml
git commit -m "Re-enable render.yaml blueprint"
git push origin main
```

Render akan ngambil `render.yaml` ini sebagai blueprint waktu kamu import repo.

---

## Step 1 — Pastikan kode di GitHub up-to-date

Kalau sudah ikuti pivot terakhir, semua sudah di `origin/main`. Cek:

```bash
git status   # harus clean atau cuma file lokal yang gitignored
git log -1   # confirm commit terakhir sudah di-push
```

---

## Step 2 — Deploy API ke Render (5 menit)

### 2a. Sign up (1 min)

1. Buka [render.com](https://render.com) → **Sign up with GitHub**.
2. Saat ditanya kartu untuk verifikasi: ini **bukan** untuk billing — free tier tetap free indefinitely. Kalau kartu utama ditolak, coba:
   - **Virtual card** dari Wise, Jenius, Revolut, atau dompet digital lain
   - **Debit card** alternatif (BCA Debit Online, Mandiri Debit, dll yang support 3DS)
   - Kartu dari bank lain
3. Selesaikan verifikasi.

### 2b. Import blueprint (3 min)

1. Dashboard Render → **New +** → **Blueprint**.
2. Pilih repo `agriflow_engine` → **Connect**.
3. Render mendeteksi `render.yaml` → tampil: *"agriflow-api · web service · Free · Python"* → klik **Apply**.
4. Build jalan ~3 menit. Lihat log di tab **Logs**.
5. Health check di `/health` harus pass otomatis.

### 2c. Copy public URL (30 detik)

URL-nya berbentuk seperti:
```
https://agriflow-api.onrender.com
```
(subdomain persis-nya bisa jadi `agriflow-api-xxxx` — copy apapun yang Render assign).

### 2d. Test (30 detik)

```bash
curl https://agriflow-api.onrender.com/health
# → {"status":"ok","engine":"loaded", ...}

curl "https://agriflow-api.onrender.com/api/v1/matches?commodity=cabai_merah"
# → JSON dengan matches
```

> **Render free-tier gotcha**: service sleep setelah 15 menit idle. Request pertama setelah sleep makan ~30 detik. Dashboard akan kelihatan hang sebentar lalu nyala. Tolerable untuk demo. Kalau juri lagi nonton, hit `/health` 30 detik sebelum pitch buat warm-up.

---

## Step 3 — Deploy dashboard ke Vercel (5 min)

1. Buka [vercel.com](https://vercel.com) → **Sign up with GitHub**.
2. **Add New** → **Project** → pilih repo `agriflow_engine` yang sama.
3. **Penting**: di import screen, set **Root Directory** = `dashboard`. Vercel auto-detect Next.js begitu lihat `dashboard/package.json`.
4. Expand **Environment Variables**. Tambah:
   - **Name**: `NEXT_PUBLIC_API_URL`
   - **Value**: URL Render dari Step 2c (mis. `https://agriflow-api.onrender.com`)
   - Apply to: **Production, Preview, Development**
5. Klik **Deploy**. Build ~2 menit.
6. Hasilnya URL seperti `https://agriflow-engine.vercel.app`.
7. Buka — harusnya tampak sama persis dengan `localhost:3000` (map, data, matches).

**Kalau muncul CORS error di browser console**: CORS regex di `whatsapp_bot/server.py` sudah allow `*.vercel.app` dan `*.hf.space`. Kalau pakai custom domain, tambah ke `allow_origins` list lalu push ulang.

---

## Step 4 — Repoint Twilio webhook ke Render (2 min)

ngrok cuma buat dev. Sekarang pakai URL Render.

1. Twilio Console → **Messaging → Try it out → WhatsApp Sandbox Settings**.
2. **WHEN A MESSAGE COMES IN** → `https://agriflow-api.onrender.com/whatsapp` (POST).
3. Save.
4. Dari HP, kirim `Pira regane lombok ing Malang?` ke sandbox. Pertama kali bisa makan ~30 detik kalau Render lagi sleep. Berikutnya instan.

Setelah ini, ngrok lokal bisa di-stop — sudah tidak diperlukan.

---

## Step 5 — Set production secrets di Render (kalau mau leave mock mode)

Selama `MOCK_MODE=true` (default di `render.yaml`), tidak perlu secret apa-apa.

Kalau sudah siap pakai Gemini + Twilio asli:

1. Buka service `agriflow-api` di Render → tab **Environment**.
2. Add environment variables:
   - `GEMINI_API_KEY` — dari [aistudio.google.com](https://aistudio.google.com)
   - `TWILIO_ACCOUNT_SID` — Twilio console
   - `TWILIO_AUTH_TOKEN` — Twilio console
   - `TWILIO_WHATSAPP_FROM` — `whatsapp:+14155238886` (sandbox) atau nomor kamu
   - `MOCK_MODE=false`
3. Klik **Save Changes** — Render restart service otomatis (~30 detik).

Secrets di-inject sebagai env vars saat runtime — tidak tampil di logs, tidak ke-commit.

---

## Step 6 — Verify the loop (2 min)

| Test | Expected |
|---|---|
| Open Vercel URL | Dashboard load dengan map + 19 komoditas di dropdown |
| Pilih "Bawang Merah" | Bubbles re-color, side panel update |
| Click any kab | Sidebar filter ke matches kab itu |
| Send WA message ke sandbox | Bot bales (mungkin setelah cold start) |
| Render → tab Logs | Lihat incoming requests dari Vercel + Twilio |

---

## When teman kamu's forecast endpoint sudah jadi

Dashboard sudah support pattern-nya. Two-step integration:

1. **Teman tambah** `GET /api/v1/forecast?commodity={code}&kab_id={id}&horizon_days=7` ke FastAPI server yang sama (atau server terpisah — tapi same-server bikin deploy lebih simple). Return `[{date, p50, p10, p90}, ...]`.
2. **Dashboard**: tambah `api.forecast()` di `dashboard/app/lib/api.ts` dan `<ForecastPanel>` di sidebar. Render auto-redeploy di setiap `git push` ke main (kalau `autoDeploy: true` di `render.yaml` — itu default-nya).

Kalau forecast di service terpisah, set env var kedua `NEXT_PUBLIC_FORECAST_URL` dan split call-nya.

---

## Costs (sanity check)

| Item | Free-tier limit | Likely usage di hackathon | Margin |
|---|---|---|---|
| Vercel hobby | 100 GB bandwidth / bulan | <1 GB | 100× |
| Render free | 750 instance-hours / bulan | 720 hr kalau always-on | ketat — sleep menyelamatkan |
| Twilio Sandbox | shared number, no spend | 0 | n/a |
| Gemini 1.5 Flash | 1500 req/hari | <100 | 15× |

Free path hold sampai ~5000 concurrent users — jauh di atas kebutuhan hackathon.

---

## Apa yang masih local-only

- `whatsapp_bot/scripts/twilio_smoke.py` — dev test helper, tidak ship
- `dashboard/.env.local` — gitignored; hanya untuk `npm run dev` lokal
- ngrok — hilang setelah Step 4

## Troubleshooting

| Symptom | Fix |
|---|---|
| Kartu ditolak Render (lagi) | Coba virtual card (Wise/Jenius/Revolut) atau debit bank lain. Atau pivot ke HF Spaces — lihat [`DEPLOY.md`](DEPLOY.md). |
| Render build gagal di `pip install` | Cek `.python-version` (di repo root) = `3.12.7`. Render reject 3.13+ di free tier. |
| Render deteksi blueprint tapi tidak ada service | Pastikan `render.yaml` ada di root repo (bukan `render.yaml.disabled`). Lihat pra-syarat di atas. |
| Vercel build gagal: "Cannot find module 'react-leaflet'" | Pastikan Vercel's Root Directory = `dashboard`, bukan repo root. |
| Dashboard tampil "Failed to fetch" | `NEXT_PUBLIC_API_URL` di Vercel env vars salah, ada trailing slash, atau Render service mati. |
| CORS error di browser console | Hard-refresh; kalau tetap, cek Render service alive (`/health`). |
| WA bot timeout | Render lagi sleep; hit `/health` sekali buat wake, lalu retry. |

---

## Kalau berubah pikiran lagi

- **Render → HF Spaces**: lihat [`DEPLOY.md`](DEPLOY.md). Rename `render.yaml` → `render.yaml.disabled`, hapus service di Render dashboard, lanjut dari HF Step 2.
- **HF Spaces → Render**: panduan ini. Aktifkan kembali `render.yaml` lewat pra-syarat di atas, hapus HF Space, lanjut dari Step 2 Render.

Vercel dashboard cuma perlu update `NEXT_PUBLIC_API_URL` di Settings → Environment Variables → trigger re-deploy. Tidak ada code change.
