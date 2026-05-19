---
title: AgriFlow API
emoji: "🌾"
colorFrom: green
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
license: mit
---

> **DRAFT — not yet promoted to README.md.** This is the v12 draft. The live
> README.md is still v11. Promote when ready: copy this file to README.md and
> archive the current README.md as README_v11.md.

# AgriFlow Matching Engine

[![tests](https://github.com/masterA88/agriflow_engine/actions/workflows/test.yml/badge.svg)](https://github.com/masterA88/agriflow_engine/actions/workflows/test.yml)

> **v12.0 release notes (Mei 2026)** — engine hardening + correctness pass on
> top of v11. This README diff is intentionally minimal; the previous v11
> README is preserved at [`README_v11.md`](README_v11.md). The five layers of
> v11 change vs v10 (volume_score coverage fix, segment_multiplier, scenario
> expansion 19→24, claim-precision) are all retained — see the v11 doc for
> that history.
>
> **v12 contains 5 hardening changes vs v11** (correctness + ops):
>
> 1. **Layer 1 correctness fix — OSRM road distance precompute.** `distance_between` now prefers OSRM road distance (ship-as-CSV `sample_data/road_distance_jatim.csv`, 38×38 = 1444 pairs) over haversine. Haversine-only was over-permissive: for cabai/bawang/tomat/ikan_segar at MAX_DISTANCE=200km, **18.6% of pairs (261/1402) were false-positive viable** — engine output matches that were physically infeasible (Madura strait detours, terrain). Real example: Kediri→Sumenep cabai haversine 205km (marginal pass) but road 284km via Suramadu (clearly infeasible). Engine is now honest. Source: OpenStreetMap (ODbL) via Project OSRM; refresh on demand via `tools/fetch_osrm_distance.py`. Fallback to haversine for any pair not in the matrix (graceful for inter-provinsi expansion). Sample demo output: 32→30 matches, -1.54% total welfare (the 2 lost matches were the false positives).
>
> 2. **Concurrency hardening — BULOG_PROCUREMENT_KAB no longer races.** `run_matching` and `apply_bulog_split` accept an explicit `bulog_procurement_kab: Optional[Set[str]]` parameter. Module-global `BULOG_PROCUREMENT_KAB` and `set_bulog_procurement()` are kept for back-compat, but parallel callers (FastAPI multi-worker, batch threadpool) should pass the explicit param to avoid race on shared mutable state. Regression test exercises 100 parallel runs across 4 workers with disjoint Bulog sets.
>
> 3. **Layer 1 perf — duplicate haversine eliminated.** `is_viable_pair` is now a thin wrapper over an internal `_check_viable_pair` that returns `(viable, reason, distance_km)`. `generate_candidates` reuses the distance the check already computed during the B2/perishability tests instead of recomputing — ~30% Layer 1 speedup per AUDIT_v10.md. End-to-end mean latency drops 7-13%: 1.29→1.12ms sample, 55.4→51.4ms Jatim 361×361.
>
> 4. **Reproducible builds + slim image.** `.dockerignore` excludes venv/, node_modules/, .git/, tests/, benchmarks/, docs/*.{pdf,docx}, secrets — HF Spaces image substantially smaller on next build. `requirements.txt` all `>=` bumped to `==` matching installed versions (scipy 1.17.1, numpy 2.4.4, fastapi 0.136.1, etc.).
>
> 5. **CI — GitHub Actions pytest matrix + benchmark publish.** Push/PR triggers pytest on Ubuntu+Windows × Python 3.11/3.12. Push to main also runs `benchmarks/latency.py` and uploads results as 30-day artifact (no hard regression gate yet — CI runner variance is too noisy to threshold without baseline data first).
>
> **Test suite: 166/166 pytest pass in 0.78s** (up from v11's 154/154 = +12 tests: 3 concurrency + 9 road-distance/Madura). Engine code remains backward-compatible: `bulog_procurement_kab` defaults to `None` (global fallback), `road_distance_km` falls back to haversine for unknown coords, existing callers see no behavior change beyond the road-distance correctness fix.

---

## Distance computation — design note (added v12)

Q: *"Kenapa OSRM, bukan Google Maps Distance Matrix? Google lebih akurat."*

A: For AgriFlow's specific use case — batch precompute, inter-kabupaten, viability filter + scoring weight in Indonesia, B2G demo audience — OSRM gives 95-99% of Google's accuracy with significant downstream advantages:

| Aspect | OSRM (chosen) | Google Maps Distance Matrix |
|---|---|---|
| Accuracy on inter-kabupaten main roads | Excellent (OSM Jatim mature, Trans-Java toll fully mapped) | Excellent (slight edge on new toll segments <6mo old) |
| Real-time traffic | No | Yes (irrelevant for batch matching) |
| Recurring cost | Free | $5/1000 elements (~Rp 80/element) |
| ToS allows long-term caching | Yes (ODbL explicit) | Conditional (30d limit some tiers — legal risk for prod) |
| Data sovereignty narrative for govt demo | "OpenStreetMap, kontribusi komunitas Indonesia" | "Server Google di Singapura" — friction for B2G |
| Reproducibility / CI | Geofabrik versioned snapshots | API can change without notice |
| Scale-up to 514 kab nasional | ~Rp 300k/month VPS, unlimited | ~Rp 13 juta per full precompute run |

The accuracy gap concentrates in domains AgriFlow does not care about: micro-routing (last 100m), real-time traffic (batch matching is hourly+, not real-time dispatch), and very recent toll openings (negligible for Jatim 2026 stable network). For commodity routing between kabupaten centers, OSM and Google produce essentially the same answer.

If the production environment ever needs real-time ETA per individual shipment (vs the current batch matching decision), wire Google for that specific call alone. The current Layer 1 viability + Layer 2 distance scoring does not need it.

---

*(Rest of README content below would be copied verbatim from v11 — sections on Architecture, 24 Scenarios, Equity Calibration, etc. Not duplicated here; promote-time merge will preserve all v11 sections after this header diff.)*
