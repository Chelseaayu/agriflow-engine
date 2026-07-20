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
  <img src="https://img.shields.io/badge/tests-520%20passing-brightgreen?style=for-the-badge" alt="Tests"/>
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
| **Security** | Supabase account system (server-side JWT verification, Row Level Security on 12 tables, password reset) ready for a subscription model; the map & core features stay **open to the public** (`REQUIRE_AUTH=false`) for the judging period | ✅ |
| **Real data** | **6 real commodities** per-district: premium & medium rice, large & cayenne chilli, red & garlic onion + 5 years of PIHPS prices | ✅ |

> **Quality:** 520 automated tests pass (521 collected, 1 skipped) — the engine is tested, reproducible, and honest about its limitations (see [Testing & Scenarios](#testing--scenarios) and Phase 3).

### Snapshots

**Dashboard** — East Java map with per-district surplus/deficit bubbles, a *top matches* list, plus a **price Forecast & Anomaly** panel (all three functions on one screen):

![AgriFlow Dashboard](assets/dashboard.png)

**WhatsApp Bot** — ask prices, find buyers/suppliers, get price forecasts & anomalies via chat. Supports **Indonesian** and **Javanese** (inclusion for rural farmers):

| Indonesian | Javanese |
|:---:|:---:|
| ![WhatsApp Indonesian](assets/whatsapp-id.png) | ![WhatsApp Javanese](assets/whatsapp-jawa.png) |

## Testing & Scenarios

Because AgriFlow's output drives inter-district food allocation that touches low-HDI districts, claims of "fair" and "robust" must be re-auditable — not just narrative. The test suite locks food-balance figures as *golden numbers* (reproducibility), guards sensitive policy parameters against accidental drift (regression-safety), and tests anomaly detection adversarially.

**521 tests collected · 520 pass · 1 skipped · cross-OS on CI.**
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

The components below were **intentionally deferred** because they would be *over-engineering* at current scale. We will build them when **scaling up**:

| Phase 3 Plan | Purpose |
|---|---|
| **National scale, 514 districts** | From 38 East Java districts → all Indonesia (needs spatial partitioning + distance precompute) |
| **Exogenous forecasting** (ENSO/climate index, Ramadan calendar) | Prediction accuracy improves with climate shocks & seasonal events |
| **Qdrant / Redis / n8n** | Vector scale, caching, scheduled orchestration — when real load arrives |
| **Sahabat-AI (Javanese/Madurese) + IVR phone** | Inclusion for elderly farmers and feature-phone users |
| **Broiler chicken & eggs (real data)** | Requires complete per-district broiler & layer egg production data |

## Current Coverage (the gate is data availability, not the system)

The AgriFlow engine is **ready to process whatever data it is given**. Today's coverage is set by the **availability of public per-district data** — once the source opens up, the same pipeline processes it with no architectural change.

| Current coverage | The gate: data availability |
|---|---|
| 6 core commodities | Engine accepts any commodity; the rest await **per-district production data** published by BPS at the same granularity |
| Reference year 2022 | The latest year consistently complete across all per-district sources; newer years are simply ingested as BPS releases them |
| Meat & eggs pending | Per-district broiler/layer production data is not yet in public sources; 13 other commodities (including eggs & chicken meat) are still **synthetic placeholders** in `historical_price_stats.csv`, unreachable through the production backend (`DATA_BACKEND=csv`) |
| Chilli/onion consumption via national figures | *Per-district* consumption for these isn't published yet; **rice consumption is already per-district & used for real** |
| Tier-2 prices (non-IHK districts) | Bapanas Panel Harga is under maintenance; once the feed is restored, 30+ more districts are covered |

## Scaling Up

Scaling (national 514 districts, full multi-commodity, real-time) is **gated by the pace of public per-district data opening up — not by technical readiness.** The engine is ready; it just needs the data feeds, then scale optimization (spatial partitioning). Our approach: **prove value at province scale with real data first, then expand as data becomes available.** Foundation-model forecasting (TimesFM 2.0) and voice/regional-language channels are scheduled enhancements for the next phase.

## Quantified engineering debt (scheduled fixes)

We measured these two limitations against this engine's own achievable ceiling ourselves, not just claimed them. The numbers come from benchmarks committed in this repo, reproducible by a judge.

**1. Optimal allocator (min-cost-flow / optimal transport).**

The shipped greedy/stable allocator is provably not optimal. Measured against an exact LP transportation optimum, on the real BPS data: the stable tier leaves 25.4% of equity-weighted welfare on the table, the greedy tier 11.1%. Benchmark: [`benchmarks/greedy_vs_optimal.py`](benchmarks/greedy_vs_optimal.py) (seeded, reproducible, calls the engine's own functions).

Concrete evidence on the real data: Sumenep's cabai_merah demand is only 26% filled, even though reachable supply (2,662 t within the 200 km limit) exceeds its need (1,418 t). The greedy allocator committed that supply elsewhere first. So this is not a scarcity problem, it's an allocation-optimality problem.

Planned fix: replace greedy with a capacitated min-cost-flow / entropic-OT solver (milliseconds at province scale, provably optimal, and the dual gives per-district shadow prices). Greedy stays as the shipped v1.

Root cause: `stable_match_tier1` is one-to-one and records min(supply, deficit) (`matching_engine/allocation.py:307`), so a large surplus matched to a small deficit strands the remainder.

**2. Unify the anomaly detector.**

There are two price-anomaly detectors in the codebase. The user-facing panel, in the dashboard/API, already uses a robust, season-aware method, S-H-ESD (`analysis/price_anomaly.py`). That one is good, and this README already praises it. The problem is a second, internal detector: the engine's D3 pre-filter gate (`matching_engine/engine.py:62`, `detect_price_anomaly`) uses a non-robust 3σ z-score against a static threshold. Measured against 70,953 real PIHPS observations, it recalls only 14.4% of the validated persistent anomalies the S-H-ESD detector finds. A D3 flag excludes a node from matching entirely, so a weak gate silently drops real supply/demand. Benchmark: [`benchmarks/anomaly_detector_gap.py`](benchmarks/anomaly_detector_gap.py).

Planned fix: retire the second detector, and have the D3 stage consume the same validated S-H-ESD output the dashboard uses. This requires reshaping the `historical_prices` contract, from commodity→(median,std) to (city,commodity,date), so it's an architecture change scheduled for Phase 3, not a hot-patch.

---

## Running (quick technical)

```bash
pip install -r requirements.txt
python examples/run_demo_real.py   # matching demo on real BPS 2022 data
pytest tests/                      # 520 pass, 1 skipped
```

Full engineering detail in [`README_v12.md`](README_v12.md).

---

## License

MIT License — &copy; 2026 Hilmi. See [`LICENSE`](LICENSE).

<p align="center"><em>Detect · Predict · Distribute — for Indonesian food security.</em></p>
