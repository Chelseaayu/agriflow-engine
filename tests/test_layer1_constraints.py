"""
Unit tests Layer 1 — Hard Constraints.
Test setiap rule constraint secara isolated.
"""
import pytest
from matching_engine.constraints import (
    haversine_km, distance_between, is_viable_pair,
    generate_candidates, ConstraintReason,
    set_bulog_procurement, reset_bulog_procurement,
)
from matching_engine.models import EmergencyMode, LogisticsContext


# =============================================================================
# Distance calculation
# =============================================================================

class TestHaversineDistance:
    def test_same_point_zero_distance(self):
        assert haversine_km(0, 0, 0, 0) == 0.0

    def test_jakarta_surabaya_approx_700km(self):
        # Jakarta (-6.2, 106.8) → Surabaya (-7.26, 112.75)
        d = haversine_km(-6.2, 106.8, -7.26, 112.75)
        assert 650 < d < 750

    def test_surabaya_madura_approx_15km(self):
        # Surabaya → Bangkalan via Suramadu
        d = haversine_km(-7.2575, 112.7521, -7.0317, 112.7491)
        assert 10 < d < 30


# =============================================================================
# Hard constraint rules
# =============================================================================

class TestViabilityRules:
    def test_viable_short_distance(self, surabaya, sidoarjo, bawang_merah,
                                    make_supply, make_demand):
        # Surabaya → Sidoarjo, ~30km, 50t bawang merah
        s = make_supply(sidoarjo, bawang_merah, volume=50)
        d = make_demand(surabaya, bawang_merah, volume=40)
        ok, reason = is_viable_pair(s, d)
        assert ok, f"Should be viable, got reason: {reason}"

    def test_reject_different_commodity(self, surabaya, kediri_kab, cabai_merah,
                                         bawang_merah, make_supply, make_demand):
        s = make_supply(kediri_kab, cabai_merah, volume=20)
        d = make_demand(surabaya, bawang_merah, volume=20)
        ok, reason = is_viable_pair(s, d)
        assert not ok
        assert reason == ConstraintReason.DIFFERENT_COMMODITY

    def test_reject_same_kabupaten(self, surabaya, bawang_merah,
                                    make_supply, make_demand):
        s = make_supply(surabaya, bawang_merah, volume=50)
        d = make_demand(surabaya, bawang_merah, volume=40)
        ok, reason = is_viable_pair(s, d)
        assert not ok
        assert reason == ConstraintReason.SAME_KABUPATEN

    def test_reject_supply_below_min(self, surabaya, kediri_kab, bawang_merah,
                                      make_supply, make_demand):
        # min_viable_tons untuk bawang_merah = 2.0
        s = make_supply(kediri_kab, bawang_merah, volume=0.5)
        d = make_demand(surabaya, bawang_merah, volume=20)
        ok, reason = is_viable_pair(s, d)
        assert not ok
        assert reason == ConstraintReason.SUPPLY_BELOW_MIN

    def test_reject_demand_below_min(self, surabaya, kediri_kab, bawang_merah,
                                      make_supply, make_demand):
        s = make_supply(kediri_kab, bawang_merah, volume=20)
        d = make_demand(surabaya, bawang_merah, volume=0.5)
        ok, reason = is_viable_pair(s, d)
        assert not ok
        assert reason == ConstraintReason.DEMAND_BELOW_MIN

    def test_reject_distance_exceeds_max(self, surabaya, banyuwangi, cabai_merah,
                                          make_supply, make_demand):
        # Banyuwangi → Surabaya ~ 290km, > 200km max untuk cabai
        s = make_supply(banyuwangi, cabai_merah, volume=10)
        d = make_demand(surabaya, cabai_merah, volume=10)
        ok, reason = is_viable_pair(s, d)
        assert not ok
        assert reason == ConstraintReason.DISTANCE_EXCEEDS_MAX

    def test_reject_unreachable_supply_disaster(self, surabaya, lumajang, bawang_merah,
                                                 make_supply, make_demand):
        # Skenario D4 — Lumajang erupsi, kab tidak reachable
        lumajang.emergency_mode = EmergencyMode.UNREACHABLE
        s = make_supply(lumajang, bawang_merah, volume=20)
        d = make_demand(surabaya, bawang_merah, volume=20)
        ok, reason = is_viable_pair(s, d)
        assert not ok
        assert reason == ConstraintReason.SUPPLY_UNREACHABLE

    def test_reject_pemda_override(self, surabaya, kediri_kab, cabai_merah,
                                    make_supply, make_demand):
        # Skenario E2 — Pemda Kediri set do_not_export
        kediri_kab.pemda_overrides["do_not_export_cabai_merah"] = True
        s = make_supply(kediri_kab, cabai_merah, volume=20)
        d = make_demand(surabaya, cabai_merah, volume=20)
        ok, reason = is_viable_pair(s, d)
        assert not ok
        assert reason == ConstraintReason.PEMDA_OVERRIDE

    def test_reject_supply_too_old(self, surabaya, banyuwangi, cabai_merah,
                                    make_supply, make_demand):
        # Cabai panen umur 5 hari = max_fresh_age, tidak akan sampai segar
        # Pakai pasangan yang lolos distance
        from matching_engine.models import Kabupaten, Tier
        # buat supplier dekat tapi cabai sudah tua
        nearby = Kabupaten(id="3506", nama="KediriKab", latitude=-7.79,
                            longitude=112.17, ipm=74.5, tier=Tier.MEDIUM)
        s = make_supply(nearby, cabai_merah, volume=10, age=5)
        d = make_demand(surabaya, cabai_merah, volume=10)
        ok, reason = is_viable_pair(s, d)
        assert not ok
        assert reason == ConstraintReason.SUPPLY_TOO_OLD


class TestBBMDistanceShrink:
    """Skenario E5: BBM naik shrinks effective max_distance."""

    def test_bbm_normal_max_distance_full(self, surabaya, kediri_kab, bawang_merah,
                                           logistics_normal, make_supply, make_demand):
        # Kediri → Surabaya ~120km, max 400km untuk bawang merah, harusnya OK
        s = make_supply(kediri_kab, bawang_merah, volume=20)
        d = make_demand(surabaya, bawang_merah, volume=20)
        ok, _ = is_viable_pair(s, d, logistics_normal)
        assert ok

    def test_bbm_naik_shrinks_threshold(self, surabaya, kediri_kab, bawang_merah,
                                         logistics_bbm_naik_20pct, make_supply, make_demand):
        # 20% BBM naik → effective max = 400 * (1 - 0.10) = 360km, masih cukup untuk 120km
        s = make_supply(kediri_kab, bawang_merah, volume=20)
        d = make_demand(surabaya, bawang_merah, volume=20)
        ok, _ = is_viable_pair(s, d, logistics_bbm_naik_20pct)
        assert ok  # masih dalam batas


# =============================================================================
# Candidate generation
# =============================================================================

class TestCandidateGeneration:
    def test_empty_inputs_returns_empty(self):
        out = generate_candidates([], [])
        assert out == []

    def test_filters_by_commodity(self, surabaya, kediri_kab, cabai_merah,
                                   bawang_merah, make_supply, make_demand):
        # Cabai surplus + bawang demand → tidak match
        s = make_supply(kediri_kab, cabai_merah, volume=10)
        d = make_demand(surabaya, bawang_merah, volume=10)
        out = generate_candidates([s], [d])
        assert len(out) == 0

    def test_basic_match_generated(self, surabaya, kediri_kab, cabai_merah,
                                    make_supply, make_demand):
        s = make_supply(kediri_kab, cabai_merah, volume=10)
        d = make_demand(surabaya, cabai_merah, volume=10)
        out = generate_candidates([s], [d])
        assert len(out) == 1
        assert out[0][0].kabupaten.id == kediri_kab.id
        assert out[0][1].kabupaten.id == surabaya.id

    def test_top_k_limit(self, kediri_kab, cabai_merah, make_supply, make_demand,
                         surabaya, sidoarjo, gresik, sumenep, banyuwangi):
        # 1 surplus, 5 deficits — top_k_per_surplus=2 → hanya 2 candidate
        s = make_supply(kediri_kab, cabai_merah, volume=100)
        # Note: sumenep & banyuwangi mungkin gagal distance, jadi tidak masuk
        deficits = [
            make_demand(k, cabai_merah, volume=5)
            for k in [surabaya, sidoarjo, gresik, sumenep, banyuwangi]
        ]
        out = generate_candidates([s], deficits, top_k_per_surplus=2)
        assert len(out) <= 2


# =============================================================================
# Bulog procurement priority handling (skenario E3 di constraints level)
# =============================================================================

class TestBulogIntegration:
    def teardown_method(self):
        reset_bulog_procurement()

    def test_set_and_reset_bulog_kab(self):
        set_bulog_procurement({"3519", "3521"})  # Madiun, Ngawi
        from matching_engine.constraints import BULOG_PROCUREMENT_KAB
        assert "3519" in BULOG_PROCUREMENT_KAB
        assert "3521" in BULOG_PROCUREMENT_KAB

        reset_bulog_procurement()
        assert len(BULOG_PROCUREMENT_KAB) == 0
