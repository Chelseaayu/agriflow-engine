Language / Bahasa: **English** · [Bahasa Indonesia](./README.md)

<p align="center"><img src="assets/logo-mark.png" alt="AgriFlow logo" width="300"/></p>

<h1 align="center">AgriFlow</h1>

<p align="center">
  <strong>AI-Powered Food Security Intelligence Platform</strong><br/>
  <em>Inter-Regional Agricultural Supply–Demand Matching Platform</em>
</p>

<p align="center"><b>Detect · Predict · Distribute</b></p>

<p align="center">
  <img src="https://img.shields.io/badge/PIDI-DIGDAYA%20%C3%97%20Hackathon%202026-1B5E20?style=for-the-badge" alt="Hackathon"/>
  <img src="https://img.shields.io/badge/Problem%20Statement-2%20Matching%20Demand–Supply-4CAF50?style=for-the-badge" alt="PS"/>
  <img src="https://img.shields.io/badge/tests-523%20passing-brightgreen?style=for-the-badge" alt="Tests"/>
</p>

> **Project roadmap spans 3 Phases.** Full technical documentation from previous versions is archived at [`README_v13.md`](README_v13.md) (latest snapshot), [`README_v12.md`](README_v12.md), and [`README_v11.md`](README_v11.md).

---

<details>
<summary><b>🖼️ View Research Poster (click to expand)</b></summary>

<br/>

<p align="center"><img src="poster/agriflow-poster.jpg" alt="AgriFlow Research Poster" width="100%"/></p>

</details>

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
| Dashboard (Live Demo) | [agriflow-engine.vercel.app](https://agriflow-engine.vercel.app/) |
| Proposal (v13) | [docs/AgriFlow_Proposal_v13.pdf](docs/AgriFlow_Proposal_v13.pdf) |

---

# Supporting Evidence — Judge Navigation

All of AgriFlow's supporting evidence sits in one place, organised along the five categories in
the submission guide. Entry point: **[docs/evidence/](docs/evidence/README.md)**.

| # | Category | In short | Status |
|---|---|---|---|
| 1 | [**Digital product**](docs/evidence/produk-digital.md) | Live dashboard, production API with recorded real responses, runnable 4-layer rule engine, WhatsApp bot | 8 of 9 items |
| 2 | [**Testing**](docs/evidence/pengujian.md) | 523 tests passing, 10.8% MAPE, performance tests, A/B test, 24 simulations, security testing, error logs, audit | 10 of 11 items |
| 3 | [**Users**](docs/evidence/pengguna.md) | 5 early testers (100% task success, 4.4-4.8 scores), 4 audio-recorded farmer interviews, testimonials | 7 of 8 items |
| 4 | [**Non-digital implementation**](docs/evidence/implementasi-non-digital.md) | Method demonstration, field observation | 2 of 9 items |
| 5 | [**External readiness**](docs/evidence/kesiapan-pihak-luar.md) | Signed BRIN pilot-willingness letter, domain-expert validation, official data-access provenance | 4 of 7 items |

**Four fastest links:** [live production API responses](docs/evidence/runs/api-live-responses.md) ·
[real BPS data demo](docs/evidence/runs/demo_real_bps.txt) ·
[5 early-tester sessions](docs/evidence/usability-early-testing.md) ·
[full audit](docs/AgriFlow_Audit_2026-07.pdf)

Category 4 is our thinnest, and we say so plainly, as we do with every unflattering finding on
those pages.

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
| **Predict** | 30-day price forecasting. What is **served today** is a seasonal-naive baseline (`seasonal_naive_baseline`) at **10.8% MAPE** on a [holdout backtest](docs/evidence/pengujian.md#3-model-evaluation). The TimesFM 2.0 pipeline is in the repo but **not yet serving production** | ✅ |
| **Accessibility** | **WhatsApp Chatbot** (ask price & recommendations) + **interactive map Dashboard** | ✅ |
| **Security** | The site is *login-first*: opening it shows a login page. Judges click **"Masuk sebagai Tamu" (Enter as Guest)** to review without creating an account. A Supabase account system (server-side JWT verification, Row Level Security on 12 tables, password reset) is ready for a subscription model; sensitive subscriber & billing data stays JWT-protected server-side. | ✅ |
| **Real data** | **6 real commodities** per-district: premium & medium rice, large & cayenne chilli, red & garlic onion + 5 years of PIHPS prices | ✅ |

> **Quality:** 523 automated tests pass (524 collected, 1 skipped) — the engine is tested, reproducible, and honest about its limitations (see [Testing & Scenarios](#testing--scenarios) and Phase 3).
>
> 📁 Full evidence lives in [**Supporting Evidence**](#supporting-evidence--judge-navigation) above: five categories, including [testing evidence](docs/evidence/pengujian.md) and [usability testing with 5 real users](docs/evidence/usability-early-testing.md).

### Snapshots

**Dashboard** — East Java map with per-district surplus/deficit bubbles, a *top matches* list, plus a **price Forecast & Anomaly** panel (all three functions on one screen):

![AgriFlow Dashboard](assets/dashboard.png)

**WhatsApp Bot** — ask prices, find buyers/suppliers, get price forecasts & anomalies via chat. Supports **Indonesian** and **Javanese** (inclusion for rural farmers):

| Indonesian | Javanese |
|:---:|:---:|
| ![WhatsApp Indonesian](assets/whatsapp-id.png) | ![WhatsApp Javanese](assets/whatsapp-jawa.png) |

## Testing & Scenarios

Because AgriFlow's output drives inter-district food allocation that touches low-HDI districts, claims of "fair" and "robust" must be re-auditable — not just narrative. The test suite locks food-balance figures as *golden numbers* (reproducibility), guards sensitive policy parameters against accidental drift (regression-safety), and tests anomaly detection adversarially.

**524 tests collected · 523 pass · 1 skipped · cross-OS on CI.** ([raw output](docs/evidence/runs/pytest.txt))
(Skip = `test_timesfm_importorskip`: skipped when the heavy TimesFM library isn't installed on the runner; the forecasting path is still tested via fallback + API contract.)

The production server loads **real BPS data by default** (`DATA_BACKEND=csv`, the default). The old synthetic 19-commodity fixture is still used by 13 test files (`DATA_BACKEND=demo`) to exercise engine logic across a wider commodity range — it is never served to users.

| Category | Count | Coverage |
|---|---|---|
| Per-layer unit (L0–L3) | 73 | IPM tier, distance/perishability constraints, scoring, equity allocation |
| 24 edge-case scenarios (A–F) | 27+ | Volume, spatial, temporal, disruption, political, quality |
| Real BPS/PIHPS data validation | 57 | Rice + horticulture 2022 food-balance, reproducible pipeline |
| Price anomaly detection | 49 | Season-aware S-H-ESD on deseasonalized residuals |
| Forecast & API | 40 | Forecast/anomaly endpoints + fallback |
| Baseline & equity | 39 | greedy/uniform/proportional vs AgriFlow + supply-constrained scenario |
| Ingest & integration | 73 | DB loader, PIHPS ingest, OSRM distance, WhatsApp bot |
| Dashboard auth & WhatsApp quota | 117 | Supabase login, server-side JWT verification, RLS on 12 tables, password reset, WhatsApp free-tier quota (disabled by default) |

The **24 edge-case scenarios** map to real East Java events, e.g.: Ramadan spike (C1), Mt. Semeru eruption in Lumajang → unreachable (D4), multi-district flood of rice belts (D5), fuel-price hike → higher logistics cost (E5), and Bulog contract-reserve priority (E3).

**Key results:**
- **Equity proven under scarcity, at zero efficiency cost.** *This is a hypothetical stress test, not a result from the real BPS data:* on the 2022 data East Java is in fact heavily in surplus (6.6× ratio), so the equity value would not surface. To show how the mechanism works we built a synthetic scarcity scenario (the `surplus_deficit_constrained.csv` fixture, surplus 3962t vs deficit 5249t). In it, pure greedy abandons Madura — Sampang **0%**, Bangkalan **20%**; AgriFlow lifts both to **100%** at *identical aggregate coverage* (0.6649), with Gini dropping (0.3017 → 0.2905). We do not claim an equity advantage under abundance, nor that this scenario comes from real data.
- **Season-aware anomalies.** A ~60% price drop is flagged, but a pure seasonal pattern (pre-Eid cycle) does **not** trigger false positives; genuine anomalies riding on top of the seasonal pattern are still caught.
- **The data reveals a structural deficit, not a bug.** Garlic (bawang putih) produces **0 matches** across all 38 districts on the 2022 BPS data — East Java is deficit in garlic in every district, consistent with Indonesia being a net garlic importer. The engine is working correctly; the data is what's speaking.

📄 Full detail (why, the 24-scenario list, paper citations): [Architecture Document](docs/AgriFlow_Architecture.pdf) §Testing & Validation.

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

Phase 3 covers two things we keep honestly separate: features we intentionally deferred because they aren't needed at the current scale, and limits we've measured on the running engine and scheduled fixes for.

## What's deferred (waiting on data or real load)

| Plan | Purpose | Trigger |
|---|---|---|
| National scale, 514 districts | From 38 East Java districts to all of Indonesia | spatial partitioning + distance precompute |
| Exogenous forecasting (ENSO index, Ramadan calendar) | Accuracy improves under climate shocks & holidays | exogenous data available |
| Broiler chicken & eggs (real data) | Completes the 6 core commodities | per-district broiler & layer-egg production data released |
| Granular per-city/market prices | Real gap can be Rp5,000 to 15,000/kg (chilli interview) | open market price feed |
| Facilitating inter-district transactions | Price info alone is "not effective enough" without a buy/sell channel (onion & rice interviews) | distribution partnership |
| Source transparency & transaction security | User-trust requirement (interviews) | formal partnership stage |
| Sahabat-AI (Javanese/Madurese) + phone IVR | Inclusion for elderly farmers & feature-phone users | channel-scaling stage |
| Qdrant / Redis / n8n | Vector scale, caching, orchestration | when real load arrives |

## Coverage limits today (the gate is data availability, not architecture)

The engine is already ready to process any data it's given; what limits it is the availability of public per-district data. Once a source opens up, the same pipeline processes it immediately with no architecture change.

| Coverage today | The gate |
|---|---|
| 6 core commodities | awaiting per-district production data for other commodities to be released by BPS |
| Reference year 2022 | the most complete year across all per-district sources; a newer year is simply ingested when available |
| Broiler chicken & eggs not yet | the other 13 commodities remain synthetic placeholders, not served to users (`DATA_BACKEND=csv`) |
| Chilli/onion consumption via national figures | rice consumption is already per-district & used for real; the rest awaits publication |
| Tier-2 prices (non-IHK districts) | Bapanas Panel Harga is under maintenance; once the feed is restored, 30+ districts are covered immediately |

## Quantified engineering debt (scheduled fixes)

We measured these two limits ourselves against the engine's own achievable ceiling, with benchmarks committed and reproducible by a judge.

1. The allocator is not yet optimal. Measured against the exact LP transportation optimum on real BPS data: the stable tier leaves 25.4% of equity-weighted welfare on the table, the greedy tier 11.1%. Concrete evidence: Sumenep's cabai_merah demand is only 26% filled even though reachable supply (2,662 t within 200 km) exceeds the need (1,418 t), greedy already committed that supply elsewhere first. So this is an optimality problem, not a scarcity problem. Plan: replace with a capacitated min-cost-flow / entropic-OT solver (milliseconds at province scale, provably optimal); greedy stays as v1. Root cause: `matching_engine/allocation.py:307`. Benchmark: `benchmarks/greedy_vs_optimal.py`.
2. Unify the anomaly detectors. The user-facing anomaly panel already uses robust S-H-ESD (`analysis/price_anomaly.py`). But the internal D3 pre-filter gate (`matching_engine/engine.py:62`) still uses a non-robust 3σ z-score, on 70,953 real PIHPS observations it recalls only 14.4% of validated anomalies, and a D3 flag excludes a node from matching entirely. Plan: point D3 at the same S-H-ESD output (requires changing the `historical_prices` contract). Benchmark: `benchmarks/anomaly_detector_gap.py`.

## Scaling Up

National-scale growth is gated by the pace of public per-district data opening up, not technical readiness. Our approach: prove value at province scale with real data first, then expand as data becomes available.

---

## Running (quick technical)

```bash
pip install -r requirements.txt
python examples/run_demo_real.py   # matching demo on real BPS 2022 data
pytest tests/                      # 523 pass, 1 skipped
```

Full engineering detail in [`README_v12.md`](README_v12.md).

---

## License

MIT License — &copy; 2026 Hilmi. See [`LICENSE`](LICENSE).

<p align="center"><em>Detect · Predict · Distribute — for Indonesian food security.</em></p>
