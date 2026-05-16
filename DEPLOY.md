# Deploy AgriFlow (Vercel + Render free tier)

End-to-end deploy of the dashboard + API + WhatsApp bot using zero-cost hosting.
Read once, then click through. Total time: ~15 minutes.

## Architecture

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

- **Vercel free**: Next.js dashboard. Unlimited bandwidth at hobby tier.
- **Render free**: FastAPI server. 750 hr/mo. Sleeps after ~15 min idle → ~30s cold start on next request.
- **Twilio Sandbox**: same as before, just point the webhook at the Render URL.

---

## Step 1 — Push code to GitHub (1 min)

If you've been following along, today's session has uncommitted changes plus the deploy configs I just wrote (`render.yaml`, `.python-version`, `dashboard/.env.example`, CORS update, dashboard scaffold). Commit + push:

```bash
git add -A
git commit -m "Add dashboard (Next.js + Leaflet) + deploy configs for Vercel/Render"
git push origin main
```

If you'd rather I run that for you, say the word and I'll do it.

---

## Step 2 — Deploy API to Render (5 min)

1. Open [render.com](https://render.com) → **Sign up with GitHub**.
2. Click **New +** → **Blueprint**.
3. Pick your `agriflow_engine` repo → **Connect**.
4. Render detects `render.yaml` → shows: *"agriflow-api · web service · Free · Python"* → click **Apply**.
5. Build runs (~3 min). Watch the log. Health check at `/health` should pass.
6. Copy the public URL — looks like `https://agriflow-api.onrender.com` (the exact subdomain might be `agriflow-api-xxxx`; copy whatever Render assigns).
7. Test it: open `https://agriflow-api.onrender.com/health` in a browser — should return JSON.

**Render free-tier gotcha**: the service sleeps after 15 min idle. Your first request after sleep takes ~30s. The dashboard will appear to hang on that first hit, then snap to life. Acceptable for demos. If a judge is watching, hit `/health` 30s before the pitch to wake it.

---

## Step 3 — Deploy dashboard to Vercel (5 min)

1. Open [vercel.com](https://vercel.com) → **Sign up with GitHub**.
2. **Add New** → **Project** → pick the same `agriflow_engine` repo.
3. **Important**: in the import screen, set **Root Directory** = `dashboard`. Vercel auto-detects Next.js once it sees `dashboard/package.json`.
4. Expand **Environment Variables**. Add:
   - **Name**: `NEXT_PUBLIC_API_URL`
   - **Value**: paste the Render URL from Step 2 (e.g. `https://agriflow-api.onrender.com`)
   - Apply to: **Production, Preview, Development**
5. Click **Deploy**. Build takes ~2 min.
6. You get a URL like `https://agriflow-engine.vercel.app` (or `https://<random>.vercel.app`).
7. Open it. Should look exactly like `localhost:3000` did — same map, same data, same matches.

**If you see CORS errors in browser console**: the CORS regex in `whatsapp_bot/server.py` already allows `*.vercel.app`. If you're using a custom domain, add it to the `allow_origins` list.

---

## Step 4 — Repoint Twilio webhook to Render (2 min)

ngrok was for dev. Now use the Render URL.

1. Twilio Console → **Messaging → Try it out → WhatsApp Sandbox Settings**.
2. **WHEN A MESSAGE COMES IN** → `https://agriflow-api.onrender.com/whatsapp` (POST).
3. Save.
4. From your phone, send `Pira regane lombok ing Malang?` to the sandbox. First time may take ~30s if Render was sleeping. Subsequent replies are instant.

You can now kill the local ngrok process — it's no longer needed.

---

## Step 5 — Verify the loop (2 min)

| Test | Expected |
|---|---|
| Open Vercel URL | Dashboard loads with map + 19 commodities in dropdown |
| Pick "Bawang Merah" | Bubbles re-color, side panel updates |
| Click any kab | Sidebar filters to that kab's matches |
| Send WA message to sandbox | Bot replies (after potential cold start) |
| Render → Logs tab | See incoming requests from Vercel + Twilio |

---

## When your friend's forecast endpoint lands

The dashboard already supports the pattern. Two-step integration:

1. **Friend adds** `GET /api/v1/forecast?commodity={code}&kab_id={id}&horizon_days=7` to the same FastAPI server (or a separate one — but same-server keeps the deploy story simple). Returns `[{date, p50, p10, p90}, ...]`.
2. **Dashboard**: add `api.forecast()` to `dashboard/app/lib/api.ts` and a `<ForecastPanel>` component in the sidebar. Both deploys re-deploy automatically on `git push`.

If forecast lives in a separate service, set a second env var `NEXT_PUBLIC_FORECAST_URL` and split the calls.

---

## Costs (sanity check)

| Item | Free-tier limit | Likely usage at hackathon | Margin |
|---|---|---|---|
| Vercel hobby | 100 GB bandwidth / mo | <1 GB | 100× |
| Render free | 750 instance-hours / mo | 720 hr if always-on | tight — sleeps save you |
| Twilio Sandbox | shared number, no spend | 0 | n/a |
| Gemini 1.5 Flash | 1500 req/day | <100 | 15× |

Free path holds until ~5000 concurrent users — well past hackathon needs.

---

## What's still local-only

- `whatsapp_bot/scripts/twilio_smoke.py` — dev test helper, doesn't ship
- `dashboard/.env.local` — gitignored; only used when running `npm run dev` locally
- ngrok — gone after Step 4

## Troubleshooting

| Symptom | Fix |
|---|---|
| Render build fails on `pip install` | Check `.python-version` is 3.12.7 (Render rejects 3.13+ on free tier) |
| Vercel build fails: "Cannot find module 'react-leaflet'" | Make sure Vercel's Root Directory is `dashboard`, not repo root |
| Dashboard shows "Failed to fetch" | `NEXT_PUBLIC_API_URL` in Vercel env vars is wrong or has trailing slash |
| CORS error in browser console | Hard-refresh; if persists, check the Render service is alive (`/health`) |
| WA bot times out | Render is asleep; hit `/health` once to wake it, then retry |
