"""
Unit tests Layer 2 (Multi-Objective Scoring).
Section 5.5.4 — bobot Distance 22% / Volume 22% / Price 22% / Perishability 18% / Climate 16%
"""
import pytest

from matching_engine.scoring import (
    DEFAULT_WEIGHTS, RAMADAN_WEIGHTS, IMPORT_POLICY_WEIGHTS,
    climate_score, compute_score, distance_score,
    estimate_logistics_cost_per_kg, perishability_score,
    price_score, volume_score,
)
from matching_engine.models import LogisticsContext, WeatherForecast


# =============================================================================
# DISTANCE SCORE
# =============================================================================

class TestDistanceScore:
    def test_short_distance_high_score(self, surabaya, sidoarjo, cabai_merah, make_supply, make_demand):
        s = make_supply(sidoarjo, cabai_merah)
        d = make_demand(surabaya, cabai_merah)
        score, dist = distance_score(s, d)
        assert dist < 30  # Sidoarjo-Surabaya ~22 km
        assert score > 0.85

    def test_long_distance_low_score(self, pacitan, banyuwangi, beras_premium, make_supply, make_demand):
        # Pacitan (barat) - Banyuwangi (timur) ~400km, max_distance beras = 800km
        s = make_supply(pacitan, beras_premium)
        d = make_demand(banyuwangi, beras_premium)
        score, dist = distance_score(s, d)
        assert dist > 350
        assert score < 0.6  # ~0.5 expected

    def test_score_is_zero_at_max_distance(self, surabaya, banyuwangi, cabai_merah, make_supply, make_demand):
        s = make_supply(banyuwangi, cabai_merah)  # ~280km > max 200km
        d = make_demand(surabaya, cabai_merah)
        score, _ = distance_score(s, d)
        assert score == 0.0


# =============================================================================
# VOLUME SCORE
# =============================================================================

class TestVolumeScore:
    def test_perfect_match(self, surabaya, kediri_kab, cabai_merah, make_supply, make_demand):
        s = make_supply(kediri_kab, cabai_merah, volume=50)
        d = make_demand(surabaya, cabai_merah, volume=50)
        assert volume_score(s, d) == 1.0

    def test_drastic_mismatch_low_score(self, surabaya, kediri_kab, cabai_merah, make_supply, make_demand):
        # Skenario A3: 5 ton supply vs 100 ton demand
        s = make_supply(kediri_kab, cabai_merah, volume=5)
        d = make_demand(surabaya, cabai_merah, volume=100)
        score = volume_score(s, d)
        assert score == 0.05  # 5/100

    def test_supply_larger_than_demand(self, surabaya, kediri_kab, cabai_merah, make_supply, make_demand):
        s = make_supply(kediri_kab, cabai_merah, volume=200)
        d = make_demand(surabaya, cabai_merah, volume=50)
        # matched=50, larger=200, score=0.25
        assert volume_score(s, d) == pytest.approx(0.25)


# =============================================================================
# PRICE SCORE & LOGISTICS COST
# =============================================================================

class TestPriceScore:
    def test_arbitrage_positive_high_score(self, surabaya, kediri_kab, cabai_merah,
                                            make_supply, make_demand, logistics_normal):
        # 30 → 60 ribu (selisih 100%) jarak ~70km, harus score tinggi
        s = make_supply(kediri_kab, cabai_merah, price=30000)
        d = make_demand(surabaya, cabai_merah, price=60000)
        score = price_score(s, d, distance_km=70, logistics=logistics_normal)
        assert score > 0.9  # arbitrage net >50%

    def test_arbitrage_negative_zero_score(self, surabaya, kediri_kab, cabai_merah,
                                            make_supply, make_demand, logistics_normal):
        # Demand < supply → lossy
        s = make_supply(kediri_kab, cabai_merah, price=50000)
        d = make_demand(surabaya, cabai_merah, price=40000)
        score = price_score(s, d, distance_km=70, logistics=logistics_normal)
        assert score == 0.0

    def test_logistics_cost_per_kg_increases_with_distance(self, logistics_normal):
        cost_short = estimate_logistics_cost_per_kg(50, logistics_normal)
        cost_long = estimate_logistics_cost_per_kg(500, logistics_normal)
        assert cost_long > cost_short

    def test_bbm_naik_increases_cost(self, logistics_normal, logistics_bbm_naik_20pct):
        # Skenario E5
        cost_normal = estimate_logistics_cost_per_kg(200, logistics_normal)
        cost_bbm_naik = estimate_logistics_cost_per_kg(200, logistics_bbm_naik_20pct)
        assert cost_bbm_naik > cost_normal


# =============================================================================
# PERISHABILITY SCORE
# =============================================================================

class TestPerishabilityScore:
    def test_fresh_short_transit_high_score(self, surabaya, kediri_kab, cabai_merah,
                                              make_supply, make_demand, logistics_normal):
        # cabai max_fresh=5 hari, age=0, transit jarak pendek → margin ~4.9 hari
        # Score = min(1.0, 4.9/5.0) = ~0.98
        s = make_supply(kediri_kab, cabai_merah, age=0)
        d = make_demand(surabaya, cabai_merah)
        score = perishability_score(s, d, distance_km=50, logistics=logistics_normal)
        assert score > 0.9  # near maksimum

    def test_too_old_zero_score(self, surabaya, kediri_kab, cabai_merah,
                                  make_supply, make_demand, logistics_normal):
        # cabai max_fresh = 5 hari, age=4, transit ~1 hari, sisa 0 hari
        s = make_supply(kediri_kab, cabai_merah, age=4)
        d = make_demand(surabaya, cabai_merah)
        score = perishability_score(s, d, distance_km=70, logistics=logistics_normal)
        assert score == 0.0  # margin < 1 hari

    def test_beras_long_shelf_always_high(self, surabaya, kediri_kab, beras_premium,
                                            make_supply, make_demand, logistics_normal):
        s = make_supply(kediri_kab, beras_premium, age=0)
        d = make_demand(surabaya, beras_premium)
        score = perishability_score(s, d, distance_km=200, logistics=logistics_normal)
        assert score == 1.0


# =============================================================================
# CLIMATE SCORE
# =============================================================================

class TestClimateScore:
    def test_no_forecast_neutral(self, surabaya, kediri_kab, cabai_merah, make_supply, make_demand):
        s = make_supply(kediri_kab, cabai_merah)
        d = make_demand(surabaya, cabai_merah)
        assert climate_score(s, d, weather=None) == 0.7

    def test_clear_weather_full_score(self, surabaya, kediri_kab, cabai_merah, make_supply, make_demand):
        s = make_supply(kediri_kab, cabai_merah)
        d = make_demand(surabaya, cabai_merah)
        wf = WeatherForecast(origin_kab_id="3506", dest_kab_id="3578", max_rain_mm=5.0)
        assert climate_score(s, d, weather=wf) == 1.0

    def test_heavy_rain_low_score(self, surabaya, kediri_kab, cabai_merah, make_supply, make_demand):
        # Skenario D1
        s = make_supply(kediri_kab, cabai_merah)
        d = make_demand(surabaya, cabai_merah)
        wf = WeatherForecast(origin_kab_id="3506", dest_kab_id="3578", max_rain_mm=75.0)
        assert climate_score(s, d, weather=wf) == 0.3

    def test_medium_rain_mid_score(self, surabaya, kediri_kab, cabai_merah, make_supply, make_demand):
        s = make_supply(kediri_kab, cabai_merah)
        d = make_demand(surabaya, cabai_merah)
        wf = WeatherForecast(origin_kab_id="3506", dest_kab_id="3578", max_rain_mm=30.0)
        assert climate_score(s, d, weather=wf) == 0.6


# =============================================================================
# COMPUTE SCORE — full weighted total
# =============================================================================

class TestComputeScore:
    def test_default_weights_sum_to_one(self):
        assert sum(DEFAULT_WEIGHTS.values()) == pytest.approx(1.0)

    def test_ramadan_weights_sum_to_one(self):
        assert sum(RAMADAN_WEIGHTS.values()) == pytest.approx(1.0)

    def test_import_policy_weights_sum_to_one(self):
        assert sum(IMPORT_POLICY_WEIGHTS.values()) == pytest.approx(1.0)

    def test_default_weights_match_section_5_5_4(self):
        # Bobot Section 5.5.4: 22/22/22/18/16
        assert DEFAULT_WEIGHTS["distance"] == 0.22
        assert DEFAULT_WEIGHTS["volume"] == 0.22
        assert DEFAULT_WEIGHTS["price"] == 0.22
        assert DEFAULT_WEIGHTS["perishability"] == 0.18
        assert DEFAULT_WEIGHTS["climate"] == 0.16

    def test_compute_score_returns_breakdown_and_total(self, surabaya, kediri_kab, cabai_merah,
                                                          make_supply, make_demand, logistics_normal):
        s = make_supply(kediri_kab, cabai_merah, volume=50, price=30000, age=0)
        d = make_demand(surabaya, cabai_merah, volume=50, price=60000)
        breakdown, base, dist = compute_score(s, d, logistics=logistics_normal)
        # All 5 dims should be > 0 for a healthy match
        assert breakdown.distance > 0
        assert breakdown.volume == 1.0
        assert breakdown.price > 0.5
        assert breakdown.perishability > 0.9  # cabai 5d shelf, near max
        assert 0 < base <= 100

    def test_ramadan_weights_increase_perishability_importance(self, surabaya, kediri_kab,
                                                                   cabai_merah, make_supply, make_demand,
                                                                   logistics_normal):
        # Skenario C1: bobot perishability naik dari 0.18 ke 0.22
        s = make_supply(kediri_kab, cabai_merah, age=2)
        d = make_demand(surabaya, cabai_merah)
        _, base_default, _ = compute_score(s, d, logistics=logistics_normal,
                                           weights=DEFAULT_WEIGHTS)
        _, base_ramadan, _ = compute_score(s, d, logistics=logistics_normal,
                                           weights=RAMADAN_WEIGHTS)
        # Score harus berbeda (perishability lebih dominan)
        assert base_default != base_ramadan
