Language / Bahasa: **English** · [Bahasa Indonesia](./README.md)

<h1 align="center">AgriFlow</h1>

<p align="center">
  <strong>AI-Powered Food Security Intelligence Platform</strong><br/>
  <em>Inter-Regional Agricultural Supply–Demand Matching Platform</em>
</p>

<p align="center"><b>Detect · Predict · Distribute</b></p>

<p align="center">
  <img src="https://img.shields.io/badge/PIDI-DIGDAYA%20%C3%97%20Hackathon%202026-1B5E20?style=for-the-badge" alt="Hackathon"/>
  <img src="https://img.shields.io/badge/Problem%20Statement-2%20Matching%20Demand–Supply-4CAF50?style=for-the-badge" alt="PS"/>
  <img src="https://img.shields.io/badge/tests-364%20passing-brightgreen?style=for-the-badge" alt="Tests"/>
</p>

> **Project roadmap spans 3 Phases.** Full technical documentation from previous versions is archived at [`README_v12.md`](README_v12.md) and [`README_v11.md`](README_v11.md).

---

# Phase 1 — Team & Links

## Team

| Name | Role | LinkedIn |
|------|------|----------|
| Chelsea | Data Analyst | [Chelsea](https://linkedin.com/in/chelseaayu) |
| Hilmi | Data Architect | [Hilmi](https://linkedin.com/in/hilmi888/) |
| Monika | UX Researcher | [Monika](https://linkedin.com/in/monika-hermiani) |
| Irpan | Data Engineer | [Irpan](https://linkedin.com/in/irpanpilihanrambe) |

## Links

| Resource | Link |
|----------|------|
| Pitch Deck | [Canva](https://www.canva.com/design/DAHETj2ulzg/VIvgxVkQ6I9R24ucphy2mQ/view) |
| Dashboard (Live Demo) | _(coming soon)_ |
| WhatsApp Bot | _(coming soon)_ |
| Video Demo | _(coming soon)_ |

---

# Phase 2 — What We Have Built (MVP)

## The Problem

Every year Indonesia loses trillions of rupiah in food — **40% occurs in distribution, not production**. In one district farmers throw away chilli because prices collapse; in the next district prices spike because supply is scarce. Local governments often discover the crisis **2–3 weeks too late**.

## The Solution

**AgriFlow matches surplus districts with deficit districts** — like "Uber for food", but aware of perishability, real road distances, and **equity for underserved regions**. Three core functions:

- **Detect** — find price anomalies (spikes/drops) from daily price data.
- **Predict** — forecast prices 30 days ahead.
- **Distribute** — intelligently and equitably match surplus to deficit.

## Architecture (High-Level)

```
   REAL DATA SOURCES             AGRIFLOW ENGINE                   ACCESS
  (BPS · PIHPS · OSRM)      ┌──────────────────────────┐
  production · consumption ─▶│ DETECT   price anomalies  │ ──┐
  prices · population        │ PREDICT  30-day forecast  │   ├──▶ Map dashboard
  per-district East Java     │ DISTRIBUTE 4-layer match  │   └──▶ WhatsApp bot
                             └──────────────────────────┘
```

All three functions (Detect · Predict · Distribute) share one real data source, then served via Dashboard and WhatsApp.

📄 **Full methodology detail — rationale, how it works, evaluation, validation, and paper citations: [Architecture Document (PDF)](docs/AgriFlow_Architecture.pdf).**

## Features Already Running

| Function | Feature | Status |
|----------|---------|:------:|
| **Distribute** | 4-layer matching engine (hard constraints → multi-objective scoring → equity) running on **real BPS per-district data (2022)** | ✅ |
| **Detect** | Price anomaly detection (deseasonalize + robust statistics) on daily PIHPS prices **2021–2025** | ✅ |
| **Predict** | 30-day price forecasting with **TimesFM 2.0** (time-series foundation model) | ✅ |
| **Accessibility** | **WhatsApp Chatbot** (ask price & recommendations) + **interactive map Dashboard** | ✅ |
| **Real data** | 5 real commodities per-district: rice, large & cayenne chilli, red & garlic onion + 5 years of prices | ✅ |

> **Quality:** 364 automated tests pass — the engine is tested, reproducible, and honest about its limitations (see Phase 3).

### Snapshots

**Dashboard** — East Java map with per-district surplus/deficit bubbles, a *top matches* list, plus a **price Forecast & Anomaly** panel (all three functions on one screen):

![AgriFlow Dashboard](assets/dashboard.png)

**WhatsApp Bot** — ask prices, find buyers/suppliers, get price forecasts & anomalies via chat. Supports **Indonesian** and **Javanese** (inclusion for rural farmers):

| Indonesian | Javanese |
|:---:|:---:|
| ![WhatsApp Indonesian](assets/whatsapp-id.png) | ![WhatsApp Javanese](assets/whatsapp-jawa.png) |

## Why Our Tech Stack Is LEAN (not as large as the original proposal)?

The initial proposal listed a large stack (Qdrant, LangChain, Redis, n8n, multi-cloud, etc.). After actually building, we **intentionally cut it** — *honest engineering* for current scale (38 districts in East Java):

| Original Plan | What We Use | Reason |
|---|---|---|
| Qdrant (separate vector DB) | **Supabase pgvector** | Small corpus — no need for a dedicated vector service |
| LangChain | **Gemini API directly** | RAG this simple doesn't need a heavy framework |
| Redis cache | **In-process cache** | Load doesn't require it yet; engine is deterministic |
| 5 hosting platforms | **2 (HF Spaces + Vercel)** | Fewer failure points, cheaper |

**Our principle: use what's sufficient, not what's fashionable.** Big components earn their place when scale justifies them — that's **Phase 3**.

---

# Phase 3 — Future Plans & Scaling

The components below were **intentionally deferred** because they would be *over-engineering* at current scale. We will build them when **scaling up**:

| Phase 3 Plan | Purpose |
|---|---|
| **National scale, 514 districts** | From 38 East Java districts → all Indonesia (needs spatial partitioning + distance precompute) |
| **Exogenous forecasting** (ENSO/climate index, Ramadan calendar) | Prediction accuracy improves with climate shocks & seasonal events |
| **Qdrant / Redis / n8n** | Vector scale, caching, scheduled orchestration — when real load arrives |
| **Sahabat-AI (Javanese/Madurese) + IVR phone** | Inclusion for elderly farmers and feature-phone users |
| **Broiler chicken & eggs (real data)** | Requires complete per-district broiler & layer egg production data |

## Limitations (honest, for fair evaluation)

- **Real data: 5 commodities, year 2022** — the most recent year with consistent per-district availability. Meat & eggs pending (incomplete production data).
- **Chilli & onion consumption** uses national average × population (proxy); **rice consumption is already real per-district**.
- **Highly perishable commodities (chilli)** need real-time `harvest_age` from the field — in the static demo dataset, some matches are constrained by the freshness limit.
- **Scale**: ready for province level (East Java); national 514 districts needs optimization — planned for Phase 3.
- **Prediction (TimesFM)** is still a separate module; full integration into the dashboard to follow.

## Scaling Up

Scaling (national, full multi-commodity, real-time data) happens in **Phase 3**, after Phase 2 MVP is validated in the field. Our approach: **prove value at small scale with real data first, then expand.**

---

## Running (quick technical)

```bash
pip install -r requirements.txt
python examples/run_demo_real.py   # matching demo on real BPS 2022 data
pytest tests/                      # 364 tests
```

Full engineering detail in [`README_v12.md`](README_v12.md).

---

## License

MIT License — &copy; 2026 Hilmi. See [`LICENSE`](LICENSE).

<p align="center"><em>Detect · Predict · Distribute — for Indonesian food security.</em></p>
