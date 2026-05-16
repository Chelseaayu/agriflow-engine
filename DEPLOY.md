# Deploy AgriFlow (Vercel + Hugging Face Spaces — both free, no card)

End-to-end deploy of the dashboard + API + WhatsApp bot using zero-cost hosting.
Read once, then click through. Total time: ~20 minutes.

> **Why HF Spaces instead of Render?** Render is also free but requires a card
> for identity verification (added late-2024 for abuse prevention). If your card
> doesn't go through — or you don't want to hand one over — HF Spaces is the
> cleanest no-card alternative. 16 GB RAM, no aggressive 15-min sleep, Docker-based.
>
> **Want to try Render anyway?** Full Render walkthrough lives at
> [`DEPLOY_RENDER.md`](DEPLOY_RENDER.md) (with tips for retrying with a virtual
> card if your main card was declined). The `render.yaml` is preserved as
> `render.yaml.disabled` in the repo — that doc shows how to re-enable it.

## Architecture

```
┌────────────────┐      HTTPS         ┌──────────────────────┐
│  Vercel        │ ─────────────────→ │  HF Spaces           │
│  Next.js       │                    │  FastAPI (Docker)    │
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

- **Vercel free**: Next.js dashboard. Unlimited bandwidth at hobby tier. Card optional.
- **HF Spaces free**: FastAPI server in a Docker container. **No card required.** 16 GB RAM, 2 CPU. Sleeps after ~48 hours of inactivity (much friendlier than Render's 15 min).
- **Twilio Sandbox**: same as before, just point the webhook at the HF Space URL.

---

## Step 1 — Push code to GitHub (already done if you followed last session)

Today's pivot adds a `Dockerfile`, CORS update, and disables `render.yaml`. Make sure these are committed and pushed:

```bash
git add Dockerfile DEPLOY.md whatsapp_bot/server.py render.yaml.disabled
git rm render.yaml  # if it's still tracked
git commit -m "Pivot from Render to Hugging Face Spaces (no-card free tier)"
git push origin main
```

If you'd rather I run that for you, say the word.

---

## Step 2 — Create HF Space + deploy API (8 min)

### 2a. Sign up (1 min)

1. Open [huggingface.co](https://huggingface.co) → **Sign up** (email + password; no card prompt).
2. Verify your email.

### 2b. Create the Space (2 min)

1. Click your avatar → **New Space**.
2. Fill in:
   - **Owner**: your username
   - **Space name**: `agriflow-api` (or anything; this becomes part of the URL)
   - **License**: MIT (or whatever matches your repo)
   - **SDK**: **Docker** ← critical
   - **Docker template**: **Blank**
   - **Hardware**: **CPU basic · 2 vCPU · 16 GB · FREE**
   - **Visibility**: **Public** (so Vercel and Twilio can reach it without auth)
3. Click **Create Space**.

You'll land on an empty Space with a `README.md` and a few starter files in its own git repo.

### 2c. Push the code into the Space (3 min)

HF Spaces are their own git repos. Easiest workflow: add it as a second remote.

```bash
# Replace <USER> and <SPACE> with your values from 2b.
git remote add space https://huggingface.co/spaces/<USER>/agriflow-api

# First push needs your HF user access token (Settings → Access Tokens on HF
# → "New token" → Role: "Write" → copy). When git asks for password, paste
# the token, not your HF password.
git push space main:main
```

Within ~30 seconds of the push, the Space's **Logs** tab will show:
- Docker layer build (~2-3 min — pip install dominates)
- `Uvicorn running on http://0.0.0.0:7860`
- A "Running" badge on the Space header

### 2d. Copy the public URL (1 min)

On the Space page, click the **⋯ menu → Embed this Space → Direct URL**. It looks like:

```
https://<USER>-agriflow-api.hf.space
```

That's your API base URL.

### 2e. Test it (1 min)

```bash
curl https://<USER>-agriflow-api.hf.space/health
# → {"status":"ok","engine":"loaded","gemini":"mock", ...}

curl "https://<USER>-agriflow-api.hf.space/api/v1/matches?commodity=cabai_merah"
# → JSON with matches
```

If `/health` returns ok, the FastAPI app is live. Move on.

> **Cold-start note**: HF Spaces with free CPU don't aggressively sleep like Render — typically only after ~48 hr of zero traffic. First request after sleep takes ~5-10s to wake (better than Render's 30s).

---

## Step 3 — Deploy dashboard to Vercel (5 min)

1. Open [vercel.com](https://vercel.com) → **Sign up with GitHub**. (Card optional; not required for hobby tier.)
2. **Add New** → **Project** → pick your `agriflow_engine` repo.
3. **Important**: in the import screen, set **Root Directory** = `dashboard`. Vercel auto-detects Next.js once it sees `dashboard/package.json`.
4. Expand **Environment Variables**. Add:
   - **Name**: `NEXT_PUBLIC_API_URL`
   - **Value**: your HF Space URL from Step 2d (e.g. `https://<USER>-agriflow-api.hf.space`)
   - Apply to: **Production, Preview, Development**
5. Click **Deploy**. Build takes ~2 min.
6. You get a URL like `https://agriflow-engine.vercel.app` (or `https://<random>.vercel.app`).
7. Open it. Should look exactly like `localhost:3000` did — same map, same data, same matches.

**If you see CORS errors in browser console**: the CORS regex in `whatsapp_bot/server.py` already allows `*.vercel.app` and `*.hf.space`. If you're using a custom domain, add it to the `allow_origins` list and re-push.

---

## Step 4 — Repoint Twilio webhook to HF Space (2 min)

ngrok was for dev. Now use the HF Space URL.

1. Twilio Console → **Messaging → Try it out → WhatsApp Sandbox Settings**.
2. **WHEN A MESSAGE COMES IN** → `https://<USER>-agriflow-api.hf.space/whatsapp` (POST).
3. Save.
4. From your phone, send `Pira regane lombok ing Malang?` to the sandbox. Reply within a few seconds.

You can now kill the local ngrok process — it's no longer needed.

---

## Step 5 — Set production secrets on HF Space (when leaving mock mode)

While in mock mode (default — `MOCK_MODE=true` in the Dockerfile env), no secrets needed.

When you're ready to wire up real Gemini + Twilio:

1. Open your Space → **Settings** → **Variables and secrets**.
2. Click **New secret** for each of:
   - `GEMINI_API_KEY` — from [aistudio.google.com](https://aistudio.google.com)
   - `TWILIO_ACCOUNT_SID` — Twilio console
   - `TWILIO_AUTH_TOKEN` — Twilio console
   - `TWILIO_WHATSAPP_FROM` — `whatsapp:+14155238886` (sandbox) or your number
3. Add a **public variable**: `MOCK_MODE=false`.
4. Restart the Space (Settings → **Factory rebuild**, or just push a no-op commit).

Secrets are injected as env vars at runtime — never appear in logs, never committed.

---

## Step 6 — Verify the loop (2 min)

| Test | Expected |
|---|---|
| Open Vercel URL | Dashboard loads with map + 19 commodities in dropdown |
| Pick "Bawang Merah" | Bubbles re-color, side panel updates |
| Click any kab | Sidebar filters to that kab's matches |
| Send WA message to sandbox | Bot replies within seconds |
| HF Space → Logs tab | See incoming requests from Vercel + Twilio |

---

## When your friend's forecast endpoint lands

The dashboard already supports the pattern. Two-step integration:

1. **Friend adds** `GET /api/v1/forecast?commodity={code}&kab_id={id}&horizon_days=7` to the same FastAPI server (or a separate one — but same-server keeps the deploy story simple). Returns `[{date, p50, p10, p90}, ...]`.
2. **Dashboard**: add `api.forecast()` to `dashboard/app/lib/api.ts` and a `<ForecastPanel>` component in the sidebar. Both deploys re-deploy automatically on `git push` (Vercel auto-syncs; HF requires `git push space main:main`).

If forecast lives in a separate service, set a second env var `NEXT_PUBLIC_FORECAST_URL` and split the calls.

---

## Keeping HF in sync with GitHub

Two workable patterns:

**Manual dual-push (simplest, what Step 1 sets up)**
```bash
git push origin main && git push space main:main
```

**One-liner alias** — add to your shell config:
```bash
alias ship='git push origin main && git push space main:main'
```

**GitHub Actions auto-sync (zero-touch, optional)** — create `.github/workflows/sync-to-hf.yml`:
```yaml
name: Sync to HF Space
on: { push: { branches: [main] } }
jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - run: |
          git push https://USER:${{ secrets.HF_TOKEN }}@huggingface.co/spaces/USER/agriflow-api main:main
```
Replace `USER` with your HF username and add `HF_TOKEN` to GitHub repo Settings → Secrets.

---

## Costs (sanity check)

| Item | Free-tier limit | Likely usage at hackathon | Margin |
|---|---|---|---|
| Vercel hobby | 100 GB bandwidth / mo | <1 GB | 100× |
| HF Spaces CPU basic | Unlimited hours; sleeps after ~48h idle | ~always-on during demo days | comfortable |
| Twilio Sandbox | shared number, no spend | 0 | n/a |
| Gemini 1.5 Flash | 1500 req/day | <100 | 15× |

Card-required hosts we considered and skipped:
- **Render** — card for ID; would have worked if user's card hadn't been declined. Configs kept at `render.yaml.disabled` if you ever want to switch.
- **Railway / Fly.io / Koyeb** — all require a card in 2025-2026.

Card-free hosts we considered:
- **HF Spaces** — picked. Best fit for FastAPI + Docker.
- **PythonAnywhere** — Python 3.10 max (we pin 3.12); fiddly webhook setup.
- **Replit** — free tier crippled in 2025.

---

## What's still local-only

- `whatsapp_bot/scripts/twilio_smoke.py` — dev test helper, doesn't ship
- `dashboard/.env.local` — gitignored; only used when running `npm run dev` locally
- ngrok — gone after Step 4

## Troubleshooting

| Symptom | Fix |
|---|---|
| HF build fails: `pip install` error | Open the Space's Logs tab. Most common: a package needs a system lib (`apt-get install <foo>` in Dockerfile). |
| HF build hangs | Bigger image than free tier likes. Trim `requirements.txt` or move dev-only deps out. |
| `git push space` asks for password and rejects | You need an HF **user access token** with Write role, not your account password. Settings → Access Tokens on huggingface.co. |
| Space shows "Building" forever | Cancel + factory rebuild from Space Settings. |
| Vercel build fails: "Cannot find module 'react-leaflet'" | Make sure Vercel's Root Directory is `dashboard`, not repo root. |
| Dashboard shows "Failed to fetch" | `NEXT_PUBLIC_API_URL` in Vercel env vars is wrong, has a trailing slash, or the Space isn't running. |
| CORS error in browser console | Hard-refresh; if persists, check the Space is alive (`/health`) and origin matches `*.vercel.app` or `*.hf.space`. |
| WA bot times out | The Space is asleep; hit `/health` once to wake it, then retry. |
