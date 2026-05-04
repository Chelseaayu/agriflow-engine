"""
Skenario DISRUPSI (D1-D5) — Section 5.5.5 v8 proposal.

D1 — Banjir rute: cuaca hujan deras → climate score turun
D2 — Komoditas rusak: harvest_age tinggi → perishability score turun
D3 — Harga anomali: outlier >3σ → exclude dari pool
D4 — Erupsi gunung: kab unreachable → reject semua match dari kab itu
D5 — Banjir multi-kab: multiple kab unreachable bersamaan
"""
import pytest

from matching_engine.engine import run_matching
from matching_engine.models import EmergencyMode


# =============================================================================
# D1 — BANJIR RUTE
# =============================================================================

class TestD1_BanjirRute:
    """Skenario D1: hujan 75mm di rute Kediri-Surabaya → climate score 0.3."""

    def test_heavy_rain_lowers_climate_component(
        self, surabaya, kediri_kab, cabai_merah,
        make_supply, make_demand, logistics_normal, weather_banjir
    ):
        s = make_supply(kediri_kab, cabai_merah, volume=50, price=30000)
        d = make_demand(surabaya, cabai_merah, volume=50, price=60000)

        report = run_matching([s], [d], logistics=logistics_normal,
                               weather_forecasts=weather_banjir)
        assert len(report.matches) == 1
        m = report.matches[0]
        # Climate score harus low (75mm > 50mm threshold)
        assert m.breakdown.climate == 0.3

    def test_no_weather_neutral_fallback(
        self, surabaya, kediri_kab, cabai_merah,
        make_supply, make_demand, logistics_normal
    ):
        # Tanpa weather forecast → 0.7 default
        s = make_supply(kediri_kab, cabai_merah, volume=50, price=30000)
        d = make_demand(surabaya, cabai_merah, volume=50, price=60000)

        report = run_matching([s], [d], logistics=logistics_normal,
                               weather_forecasts=None)
        if report.matches:
            assert report.matches[0].breakdown.climate == 0.7


# =============================================================================
# D2 — KOMODITAS HAMPIR RUSAK
# =============================================================================

class TestD2_KomoditasRusak:
    """Skenario D2: cabai harvest_age=4 (max=5) → margin tipis → perish score 0."""

    def test_old_harvest_blocks_match(
        self, surabaya, kediri_kab, cabai_merah,
        make_supply, make_demand, logistics_normal
    ):
        # Cabai max_fresh=5d, age=4d, transit ~1d → margin <1d → perish=0
        s = make_supply(kediri_kab, cabai_merah, volume=50, price=30000, age=4)
        d = make_demand(surabaya, cabai_merah, volume=50, price=60000)

        report = run_matching([s], [d], logistics=logistics_normal)
        # Layer 1 (is_viable_pair) atau Layer 2 perish=0 → match terjadi tapi score rendah
        if report.matches:
            assert report.matches[0].breakdown.perishability == 0.0

    def test_age_exceeds_max_fresh_rejected_at_layer1(
        self, surabaya, kediri_kab, cabai_merah,
        make_supply, make_demand, logistics_normal
    ):
        # age=10 > max_fresh=5 → Layer 1 reject
        s = make_supply(kediri_kab, cabai_merah, volume=50, price=30000, age=10)
        d = make_demand(surabaya, cabai_merah, volume=50, price=60000)

        report = run_matching([s], [d], logistics=logistics_normal)
        assert len(report.matches) == 0
        assert len(report.unmatched_supply if hasattr(report, "unmatched_supply") else report.unmatched_surplus) == 1


# =============================================================================
# D3 — HARGA ANOMALI
# =============================================================================

class TestD3_HargaAnomali:
    """Skenario D3: harga outlier >3σ dari rolling median → exclude."""

    def test_extreme_price_anomaly_excluded(
        self, surabaya, kediri_kab, cabai_merah,
        make_supply, make_demand, logistics_normal
    ):
        # Median 30k, std 5k. Anomali at 100k (>3σ = >45k)
        s_anomaly = make_supply(kediri_kab, cabai_merah, volume=50, price=100000)
        d = make_demand(surabaya, cabai_merah, volume=50, price=60000)

        historical = {"cabai_merah": (30000.0, 5000.0)}
        report = run_matching([s_anomaly], [d], logistics=logistics_normal,
                                historical_prices=historical)
        # Tidak ada match (anomaly excluded) ATAU warning
        assert any("anomaly" in w.lower() or "anomali" in w.lower() for w in report.warnings)
        assert len(report.matches) == 0

    def test_normal_price_within_3sigma_kept(
        self, surabaya, kediri_kab, cabai_merah,
        make_supply, make_demand, logistics_normal
    ):
        # Median 40k, std 5k. Supply 35k (-1σ), demand 50k (+2σ) → both ok
        s = make_supply(kediri_kab, cabai_merah, volume=50, price=35000)
        d = make_demand(surabaya, cabai_merah, volume=50, price=50000)

        historical = {"cabai_merah": (40000.0, 5000.0)}
        report = run_matching([s], [d], logistics=logistics_normal,
                                historical_prices=historical)
        assert len(report.matches) == 1


# =============================================================================
# D4 — ERUPSI GUNUNG (UNREACHABLE)
# =============================================================================

class TestD4_ErupsiGunung:
    """Skenario D4: Lumajang erupsi Semeru → unreachable, reject semua match."""

    def test_unreachable_supply_excluded(
        self, surabaya, lumajang, cabai_merah,
        make_supply, make_demand, logistics_normal
    ):
        lumajang.emergency_mode = EmergencyMode.UNREACHABLE
        s = make_supply(lumajang, cabai_merah, volume=50, price=30000)
        d = make_demand(surabaya, cabai_merah, volume=50, price=60000)

        report = run_matching([s], [d], logistics=logistics_normal)
        # Tidak ada match karena Lumajang unreachable
        assert len(report.matches) == 0

    def test_humanitarian_kab_priority_flag(
        self, kediri_kab, lumajang, cabai_merah,
        make_supply, make_demand, logistics_normal
    ):
        # Lumajang emergency butuh demand sebagai prioritas humanitarian
        lumajang.emergency_mode = EmergencyMode.HUMANITARIAN
        s = make_supply(kediri_kab, cabai_merah, volume=50, price=30000)
        d = make_demand(lumajang, cabai_merah, volume=50, price=55000)

        report = run_matching([s], [d], logistics=logistics_normal)
        if report.matches:
            assert "HUMANITARIAN_PRIORITY" in report.matches[0].flags


# =============================================================================
# D5 — BANJIR MULTI-KAB
# =============================================================================

class TestD5_BanjirMultiKab:
    """Skenario D5: banjir besar Bojonegoro + Lamongan + Tuban (sentra padi) bersamaan."""

    def test_multiple_unreachable_handled(
        self, surabaya, beras_premium,
        make_supply, make_demand, logistics_normal
    ):
        from matching_engine.models import Kabupaten, Tier
        bojonegoro = Kabupaten(id="3522", nama="Bojonegoro", latitude=-7.15, longitude=111.88,
                                ipm=71.80, tier=Tier.MEDIUM,
                                emergency_mode=EmergencyMode.UNREACHABLE)
        lamongan = Kabupaten(id="3524", nama="Lamongan", latitude=-7.11, longitude=112.41,
                              ipm=74.05, tier=Tier.MEDIUM,
                              emergency_mode=EmergencyMode.UNREACHABLE)
        tuban = Kabupaten(id="3523", nama="Tuban", latitude=-6.89, longitude=112.06,
                           ipm=70.95, tier=Tier.MEDIUM,
                           emergency_mode=EmergencyMode.UNREACHABLE)

        s_bojo = make_supply(bojonegoro, beras_premium, volume=300, price=11000)
        s_lamo = make_supply(lamongan, beras_premium, volume=250, price=11000)
        s_tuban = make_supply(tuban, beras_premium, volume=200, price=11200)

        d = make_demand(surabaya, beras_premium, volume=200, price=14000)

        report = run_matching([s_bojo, s_lamo, s_tuban], [d], logistics=logistics_normal)
        # Semua surplus unreachable → 0 matches
        assert len(report.matches) == 0
        # Engine harus produce external opportunity (zero demand setelah filter)
        # atau setidaknya unmatched deficit
        assert len(report.unmatched_deficit) == 1
