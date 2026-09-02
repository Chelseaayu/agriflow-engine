"""
tests/test_backend_v11.py -- v1.1 backend changes.

Covers:
  * LP allocator: never below greedy welfare, respects capacities
  * anomaly gate: scanner keys exclude nodes, legacy z-score untouched
  * calendar fix (audit F1): explicit Ramadan wins, import policy composes
  * new API surface: /health fields, /api/v1/meta, /summary, /report.csv,
    /matches breakdown, /matches/explain, /simulate, city alias
"""
from __future__ import annotations

import datetime as dt
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from analysis.anomaly_gate import recent_anomaly_keys
from matching_engine import LogisticsContext, run_matching
from matching_engine.allocation import lp_optimal_allocate, welfare
from matching_engine.constraints import generate_candidates
from matching_engine.scoring import (
    DEFAULT_WEIGHTS, IMPORT_POLICY_WEIGHTS, RAMADAN_WEIGHTS, SCHOOL_START_WEIGHTS,
    apply_import_policy, compute_score,
)
from sample_data.loader import load_real_data


@pytest.fixture(scope="module")
def real():
    return load_real_data()


# --------------------------------------------------------------------------
# Allocator
# --------------------------------------------------------------------------

class TestLPAllocator:
    def test_lp_welfare_not_below_greedy_on_real_data(self, real):
        greedy = run_matching(real["surplus"], real["deficit"], force_strategy="greedy",
                              weather_forecasts=real["weather"], anomaly_keys=set())
        lp = run_matching(real["surplus"], real["deficit"], force_strategy="lp",
                          weather_forecasts=real["weather"], anomaly_keys=set())
        assert lp.run_metadata["allocator"] == "lp_optimal"
        assert greedy.run_metadata["allocator"] == "greedy"
        assert lp.run_metadata["welfare"] >= greedy.run_metadata["welfare"] - 1e-6
        assert lp.run_metadata["welfare_greedy"] == pytest.approx(
            greedy.run_metadata["welfare"], rel=1e-6)
        assert lp.run_metadata["welfare_gain_pct"] >= 0

    def test_lp_respects_capacities(self, real):
        cands = generate_candidates(real["surplus"], real["deficit"], logistics=LogisticsContext())

        def score_fn(s, d):
            return compute_score(s, d, logistics=LogisticsContext(), weights=DEFAULT_WEIGHTS)

        matches = lp_optimal_allocate(cands, score_fn)
        assert matches, "LP returned no matches on real data"
        out_by_s, in_by_d = {}, {}
        for m in matches:
            sk = (m.surplus.kabupaten.id, m.surplus.commodity.code)
            dk = (m.deficit.kabupaten.id, m.deficit.commodity.code, m.deficit.segment.value)
            out_by_s[sk] = out_by_s.get(sk, 0.0) + m.matched_volume_tons
            in_by_d[dk] = in_by_d.get(dk, 0.0) + m.matched_volume_tons
            assert m.matched_volume_tons > 0
        vol_s = {(s.kabupaten.id, s.commodity.code): s.volume_tons for s in real["surplus"]}
        vol_d = {(d.kabupaten.id, d.commodity.code, d.segment.value): d.volume_tons for d in real["deficit"]}
        for k, v in out_by_s.items():
            assert v <= vol_s[k] + 1e-6
        for k, v in in_by_d.items():
            assert v <= vol_d[k] + 1e-6

    def test_lp_matches_lp_benchmark_optimum(self, real):
        """Engine LP equals the benchmark's own LP formulation within tolerance."""
        sys.path.insert(0, os.path.join(ROOT, "benchmarks"))
        from greedy_vs_optimal import solve_capacitated_transportation_lp
        cands = generate_candidates(real["surplus"], real["deficit"], logistics=LogisticsContext())

        def score_fn(s, d):
            return compute_score(s, d, logistics=LogisticsContext(), weights=DEFAULT_WEIGHTS)

        opt, _tons, status, _ = solve_capacitated_transportation_lp(cands, score_fn)
        assert status == "optimal"
        assert welfare(lp_optimal_allocate(cands, score_fn)) == pytest.approx(opt, rel=1e-6)

    def test_default_strategy_unchanged(self, real):
        """Golden numbers elsewhere rely on the v9 auto-detect staying greedy."""
        r = run_matching(real["surplus"], real["deficit"], anomaly_keys=set())
        assert r.run_metadata["allocator"] == "greedy"
        assert r.run_metadata["welfare_greedy"] is None


# --------------------------------------------------------------------------
# Anomaly gate
# --------------------------------------------------------------------------

class TestAnomalyGate:
    def test_recent_keys_window_and_persistence(self):
        recs = [
            {"date": "2025-12-30", "city_id": "3578", "commodity_code": "cabai_rawit", "persistent": True},
            {"date": "2025-12-01", "city_id": "3573", "commodity_code": "cabai_rawit", "persistent": True},
            {"date": "2025-12-31", "city_id": "3509", "commodity_code": "bawang_merah", "persistent": False},
        ]
        keys = recent_anomaly_keys(recs, window_days=14)
        assert keys == {("3578", "cabai_rawit")}
        assert recent_anomaly_keys(recs, window_days=60) == {
            ("3578", "cabai_rawit"), ("3573", "cabai_rawit")}
        assert recent_anomaly_keys(recs, window_days=14, persistent_only=False) == {
            ("3578", "cabai_rawit"), ("3509", "bawang_merah")}
        assert recent_anomaly_keys([]) == set()

    def test_gate_excludes_flagged_nodes(self, surabaya, kediri_kab, cabai_merah,
                                        make_supply, make_demand):
        s = make_supply(kediri_kab, cabai_merah, volume=50, price=30000)
        d = make_demand(surabaya, cabai_merah, volume=50, price=60000)
        clean = run_matching([s], [d], anomaly_keys=set())
        assert clean.run_metadata["anomaly_gate"] == "batch_hampel_mad"
        assert len(clean.matches) == 1
        gated = run_matching([s], [d], anomaly_keys={(kediri_kab.id, "cabai_merah")})
        assert gated.matches == []
        assert any("scanner" in w for w in gated.warnings)

    def test_legacy_zscore_when_keys_absent(self, surabaya, kediri_kab, cabai_merah,
                                            make_supply, make_demand):
        s = make_supply(kediri_kab, cabai_merah, volume=50, price=30000)
        d = make_demand(surabaya, cabai_merah, volume=50, price=60000)
        r = run_matching([s], [d], historical_prices={"cabai_merah": (40000.0, 5000.0)})
        assert r.run_metadata["anomaly_gate"] == "zscore_3sigma"
        r2 = run_matching([s], [d])
        assert r2.run_metadata["anomaly_gate"] == "none"


# --------------------------------------------------------------------------
# Calendar fix (audit F1)
# --------------------------------------------------------------------------

class TestCalendarPriority:
    def test_explicit_ramadan_beats_school_start_window(self, surabaya, kediri_kab, cabai_merah,
                                                        make_supply, make_demand, logistics_ramadan):
        s = make_supply(kediri_kab, cabai_merah, volume=50, price=30000)
        d = make_demand(surabaya, cabai_merah, volume=50, price=60000)
        r = run_matching([s], [d], logistics=logistics_ramadan,
                         reference_date=dt.datetime(2026, 7, 10))
        assert r.run_metadata["active_event"] == "RAMADAN"
        assert r.run_metadata["weights_used"] == RAMADAN_WEIGHTS

    def test_import_policy_composes_with_event(self, surabaya, kediri_kab, bawang_merah,
                                               make_supply, make_demand):
        s = make_supply(kediri_kab, bawang_merah, volume=50, price=25000)
        d = make_demand(surabaya, bawang_merah, volume=50, price=40000)
        r = run_matching([s], [d], import_policy_active=True,
                         reference_date=dt.datetime(2026, 7, 10))
        w = r.run_metadata["weights_used"]
        assert r.run_metadata["active_event"] == "SCHOOL_START"
        assert w["price"] == IMPORT_POLICY_WEIGHTS["price"]
        assert w != SCHOOL_START_WEIGHTS
        assert sum(w.values()) == pytest.approx(1.0, abs=1e-3)
        assert r.matches and "IMPORT_POLICY_ACTIVE" in r.matches[0].flags

    def test_apply_import_policy_identity_on_default(self):
        assert apply_import_policy(DEFAULT_WEIGHTS) == IMPORT_POLICY_WEIGHTS
        composed = apply_import_policy(RAMADAN_WEIGHTS)
        assert composed["price"] == 0.10
        assert sum(composed.values()) == pytest.approx(1.0, abs=1e-3)


# --------------------------------------------------------------------------
# Mock intent heuristics
# --------------------------------------------------------------------------

class TestMockCommodityDetection:
    def test_most_specific_phrase_wins(self):
        from whatsapp_bot.gemini_client import _detect_commodity
        assert _detect_commodity("Berapa harga cabai rawit di Malang?") == "cabai_rawit"
        assert _detect_commodity("harga cabe rawit surabaya") == "cabai_rawit"
        assert _detect_commodity("harga cabai merah di kediri") == "cabai_merah"
        assert _detect_commodity("harga cabai di kediri") == "cabai_merah"
        assert _detect_commodity("pira regane lombok cilik ing nganjuk") == "cabai_rawit"
        assert _detect_commodity("harga bawang putih") == "bawang_putih"
        assert _detect_commodity("beras medium surabaya") == "beras_medium"
        assert _detect_commodity("halo apa kabar") is None


# --------------------------------------------------------------------------
# API surface
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi not installed")
    os.environ.pop("ALLOCATOR", None)
    from whatsapp_bot.server import app
    with TestClient(app) as c:
        yield c


class TestApiV11:
    def test_health_reports_engine_and_data_as_of(self, client):
        body = client.get("/health").json()
        assert body["engine_version"] == "1.1.0"
        assert body["allocator"] == "lp"
        assert body["anomaly_method"] == "hampel_mad_v2"
        assert body["data_as_of"]["price_history_end"]
        assert body["data_as_of"]["bps_reference_year"] == 2022

    def test_meta(self, client):
        r = client.get("/api/v1/meta")
        assert r.status_code == 200
        body = r.json()
        assert body["allocator"] == "lp_optimal"
        assert body["anomaly_gate"] == "batch_hampel_mad"
        assert body["data_as_of"]["price_history_end"] >= "2025-12-01"
        assert body["coverage"]["kabupaten"] == 38
        assert body["engine_run"]["welfare"] is not None

    def test_matches_carry_breakdown_and_why(self, client):
        r = client.get("/api/v1/matches?commodity=bawang_merah&limit=3")
        assert r.status_code == 200
        m = r.json()["matches"][0]
        for k in ("base_score", "equity_multiplier", "breakdown", "why", "gross_arbitrage_idr"):
            assert k in m
        assert set(m["breakdown"]) == {"distance", "volume", "price", "perishability", "climate"}
        assert isinstance(m["why"], list) and m["why"]

    def test_summary_is_computed(self, client):
        r = client.get("/api/v1/summary")
        assert r.status_code == 200
        body = r.json()
        assert body["totals"]["matched_tons"] > 0
        assert 0 < body["totals"]["coverage_pct"] <= 100
        assert body["engine"]["allocator"] == "lp_optimal"
        assert "bawang_putih" in body["per_commodity"]
        assert body["per_commodity"]["bawang_putih"]["n_matches"] == 0
        r2 = client.get("/api/v1/summary?commodity=beras_premium")
        assert list(r2.json()["per_commodity"]) == ["beras_premium"]
        assert client.get("/api/v1/summary?commodity=nangka").status_code == 404

    def test_report_csv(self, client):
        r = client.get("/api/v1/report.csv?commodity=bawang_merah")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/csv")
        assert "attachment" in r.headers["content-disposition"]
        lines = r.text.strip().splitlines()
        assert lines[0].startswith("commodity_code,commodity_nama,surplus_kab_id")
        assert len(lines) > 1
        assert all(l.startswith("bawang_merah,") for l in lines[1:])

    def test_explain_ranks_suppliers(self, client):
        r = client.get("/api/v1/matches/explain?deficit_kab_id=3526&commodity=bawang_merah")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["deficit"]["kab_nama"] == "Bangkalan"
        assert body["n_viable_suppliers"] >= 1
        scores = [x["final_score"] for x in body["ranking"]]
        assert scores == sorted(scores, reverse=True)
        assert any(x["chosen"] for x in body["ranking"])
        # name alias works here too
        r2 = client.get("/api/v1/matches/explain?deficit_kab_id=Bangkalan&commodity=bawang_merah")
        assert r2.status_code == 200
        assert client.get("/api/v1/matches/explain?deficit_kab_id=9999&commodity=bawang_merah").status_code == 404

    def test_forecast_accepts_city_name(self, client):
        code = client.get("/api/v1/forecast?commodity=cabai_rawit&city=3578").json()
        name = client.get("/api/v1/forecast?commodity=cabai_rawit&city=Kota%20Surabaya").json()
        assert name["city_id"] == code["city_id"] == "3578"
        assert client.get("/api/v1/forecast?commodity=cabai_rawit&city=surabaya").status_code == 200

    def test_price_history(self, client):
        r = client.get("/api/v1/price-history?commodity=cabai_rawit&city=Kota%20Surabaya&days=90")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["city_id"] == "3578" and body["n"] == 90
        assert body["history_end_date"] == body["points"][-1]["date"]
        dates = [p["date"] for p in body["points"]]
        assert dates == sorted(dates)
        assert client.get("/api/v1/price-history?commodity=cabai_rawit&city=9999").status_code == 404

    def test_anomalies_label(self, client):
        body = client.get("/api/v1/anomalies?limit=2").json()
        assert body["method"] == "hampel_mad_v2"

    def test_simulate_semeru_removes_lumajang(self, client):
        r = client.post("/api/v1/simulate", json={"presets": ["semeru"]})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["scenario"]["applied"]["unreachable_kab"] == ["3508"]
        for m in body["matches"]:
            assert m["surplus"]["kab_id"] != "3508" and m["deficit"]["kab_id"] != "3508"
        assert body["result"]["matched_tons"] <= body["baseline"]["matched_tons"] + 1e-6
        assert "delta" in body and body["delta"]["latency_ms"] is not None

    def test_simulate_ramadan_and_bbm(self, client):
        r = client.post("/api/v1/simulate", json={"presets": ["ramadan", "bbm_20"], "commodity": "cabai_rawit"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["scenario"]["active_event"] == "RAMADAN"
        assert body["scenario"]["applied"]["bbm_pct"] == 20.0
        assert list(body["baseline"].keys()) == list(body["result"].keys())

    def test_simulate_unknown_preset_400(self, client):
        assert client.post("/api/v1/simulate", json={"presets": ["tsunami"]}).status_code == 400

    def test_simulate_presets_listed(self, client):
        body = client.get("/api/v1/simulate/presets").json()
        assert "semeru" in body and "banjir_sentra_padi" in body
