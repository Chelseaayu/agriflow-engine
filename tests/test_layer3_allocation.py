"""
Unit tests Layer 3 (Equity-Weighted Allocation).
Section 5.5.4 — Modified Gale-Shapley + Greedy Top-K + Equity Multiplier.
"""
import pytest

from matching_engine.allocation import (
    allocate, determine_confidence, equity_multiplier_value,
    greedy_match_tier2, stable_match_tier1,
)
from matching_engine.models import Confidence, ScoreBreakdown
from matching_engine.scoring import compute_score


# =============================================================================
# EQUITY MULTIPLIER
# =============================================================================

class TestEquityMultiplier:
    """
    Threshold kalibrasi BPS 2024 Jatim:
        <68 → 1.30 | <72 → 1.15 | <78 → 1.05 | ≥78 → 1.00
    """

    def test_ipm_below_68_gets_30pct_boost(self):
        """Tertinggal severe: Sampang 66.72, Bangkalan 67.70 (cluster Madura)."""
        assert equity_multiplier_value(60.0) == 1.30
        assert equity_multiplier_value(66.72) == 1.30  # Sampang real
        assert equity_multiplier_value(67.70) == 1.30  # Bangkalan real
        assert equity_multiplier_value(67.99) == 1.30

    def test_ipm_68_to_72_gets_15pct_boost(self):
        """Tertinggal: Sumenep 68.79, Bondowoso 69.62, Lumajang 70.10, Pamekasan 70.43."""
        assert equity_multiplier_value(68.0) == 1.15
        assert equity_multiplier_value(68.79) == 1.15  # Sumenep
        assert equity_multiplier_value(69.62) == 1.15  # Bondowoso
        assert equity_multiplier_value(70.10) == 1.15  # Lumajang
        assert equity_multiplier_value(70.43) == 1.15  # Pamekasan
        assert equity_multiplier_value(71.99) == 1.15

    def test_ipm_72_to_78_gets_5pct_boost(self):
        """Menengah: Banyuwangi 73.45, Kediri kab 74.50, Tulungagung 75.30, Gresik 77.61."""
        assert equity_multiplier_value(72.0) == 1.05
        assert equity_multiplier_value(73.45) == 1.05  # Banyuwangi
        assert equity_multiplier_value(74.50) == 1.05  # Kediri kab
        assert equity_multiplier_value(77.61) == 1.05  # Gresik
        assert equity_multiplier_value(77.99) == 1.05

    def test_ipm_78_or_above_no_boost(self):
        """Maju: Kota Batu 78.30, Sidoarjo 80.13, Kota Surabaya 84.69."""
        assert equity_multiplier_value(78.0) == 1.00
        assert equity_multiplier_value(78.30) == 1.00  # Kota Batu
        assert equity_multiplier_value(80.13) == 1.00  # Sidoarjo
        assert equity_multiplier_value(84.69) == 1.00  # Surabaya


# =============================================================================
# CONFIDENCE LABELING
# =============================================================================

class TestConfidence:
    def test_both_tier1_high_confidence(self, surabaya, kota_kediri, cabai_merah, make_supply, make_demand):
        s = make_supply(kota_kediri, cabai_merah)
        d = make_demand(surabaya, cabai_merah)
        assert determine_confidence(s, d) == Confidence.HIGH

    def test_cross_tier_medium(self, surabaya, kediri_kab, cabai_merah, make_supply, make_demand):
        s = make_supply(kediri_kab, cabai_merah)  # Tier 2
        d = make_demand(surabaya, cabai_merah)   # Tier 1
        assert determine_confidence(s, d) == Confidence.MEDIUM

    def test_both_tier2_medium(self, kediri_kab, sidoarjo, cabai_merah, make_supply, make_demand):
        s = make_supply(kediri_kab, cabai_merah)  # Tier 2
        d = make_demand(sidoarjo, cabai_merah)    # Tier 2
        assert determine_confidence(s, d) == Confidence.MEDIUM


# =============================================================================
# STABLE MATCHING (TIER 1)
# =============================================================================

class TestStableMatchTier1:
    def test_simple_one_to_one(self, surabaya, kota_kediri, cabai_merah,
                                  make_supply, make_demand, logistics_normal):
        s = make_supply(kota_kediri, cabai_merah, volume=50, price=30000)
        d = make_demand(surabaya, cabai_merah, volume=50, price=60000)
        candidates = [(s, d)]

        def score_fn(s_, d_):
            return compute_score(s_, d_, logistics=logistics_normal)

        results = stable_match_tier1(candidates, score_fn)
        assert len(results) == 1
        assert results[0].surplus.kabupaten.id == kota_kediri.id
        assert results[0].deficit.kabupaten.id == surabaya.id
        assert results[0].confidence == Confidence.HIGH

    def test_higher_score_wins(self, surabaya, kota_kediri, kediri_kab, cabai_merah,
                                  make_supply, make_demand, logistics_normal):
        # Surabaya butuh cabai. Dua surplus dengan price difference besar.
        # Force both jadi Tier 1 untuk uji pure stable matching:
        from matching_engine.models import Tier
        kediri_kab.tier = Tier.HIGH

        # kota_kediri price 25k (sangat murah, arbitrage tinggi)
        # kediri_kab price 50k (mahal, arbitrage rendah)
        s_cheap = make_supply(kota_kediri, cabai_merah, volume=50, price=25000)
        s_expensive = make_supply(kediri_kab, cabai_merah, volume=50, price=50000)
        d = make_demand(surabaya, cabai_merah, volume=50, price=60000)
        candidates = [(s_cheap, d), (s_expensive, d)]

        def score_fn(s_, d_):
            return compute_score(s_, d_, logistics=logistics_normal)

        results = stable_match_tier1(candidates, score_fn)
        assert len(results) >= 1
        # Best match harus s_cheap (price arbitrage jauh lebih besar)
        assert results[0].surplus.kabupaten.id == kota_kediri.id


# =============================================================================
# GREEDY MATCHING (TIER 2)
# =============================================================================

class TestGreedyMatchTier2:
    def test_equity_priority_kab_tertinggal_first(self, kediri_kab, sampang, sidoarjo,
                                                     cabai_merah, make_supply, make_demand,
                                                     logistics_normal):
        """
        Scenario E1: dua deficit kab dengan IPM berbeda.
        Sampang (IPM 66.72, +15% boost) harus dapat priority over Sidoarjo (80.13, no boost).
        """
        s = make_supply(kediri_kab, cabai_merah, volume=50, price=30000)
        d_sampang = make_demand(sampang, cabai_merah, volume=50, price=55000)
        d_sidoarjo = make_demand(sidoarjo, cabai_merah, volume=50, price=60000)

        candidates = [(s, d_sampang), (s, d_sidoarjo)]

        def score_fn(s_, d_):
            return compute_score(s_, d_, logistics=logistics_normal)

        results = greedy_match_tier2(candidates, score_fn)
        # Sampang harus jadi pemenang meskipun harga jualnya lebih rendah
        # (karena equity multiplier menggandakan score)
        assert len(results) >= 1
        # First match harus ke Sampang
        first_match = results[0]
        assert first_match.deficit.kabupaten.id == sampang.id
        assert first_match.equity_multiplier == 1.30  # Sampang IPM 66.72 < 68

    def test_volume_split_when_supply_larger(self, kediri_kab, sampang, bondowoso, cabai_merah,
                                                make_supply, make_demand, logistics_normal):
        # Surplus 100t bisa di-split ke 2 deficit @ 40t each
        s = make_supply(kediri_kab, cabai_merah, volume=100, price=30000)
        d1 = make_demand(sampang, cabai_merah, volume=40, price=55000)
        d2 = make_demand(bondowoso, cabai_merah, volume=40, price=55000)

        candidates = [(s, d1), (s, d2)]

        def score_fn(s_, d_):
            return compute_score(s_, d_, logistics=logistics_normal)

        results = greedy_match_tier2(candidates, score_fn)
        # Both deficits should be served
        assert len(results) == 2
        deficit_ids = {r.deficit.kabupaten.id for r in results}
        assert deficit_ids == {sampang.id, bondowoso.id}


# =============================================================================
# DISPATCHER
# =============================================================================

class TestAllocateDispatcher:
    def test_force_strategy_stable(self, surabaya, kota_kediri, cabai_merah,
                                      make_supply, make_demand, logistics_normal):
        s = make_supply(kota_kediri, cabai_merah)
        d = make_demand(surabaya, cabai_merah)
        candidates = [(s, d)]

        def score_fn(s_, d_):
            return compute_score(s_, d_, logistics=logistics_normal)

        results = allocate(candidates, score_fn, force_strategy="stable")
        assert len(results) == 1

    def test_force_strategy_greedy(self, surabaya, kota_kediri, cabai_merah,
                                      make_supply, make_demand, logistics_normal):
        s = make_supply(kota_kediri, cabai_merah)
        d = make_demand(surabaya, cabai_merah)
        candidates = [(s, d)]

        def score_fn(s_, d_):
            return compute_score(s_, d_, logistics=logistics_normal)

        results = allocate(candidates, score_fn, force_strategy="greedy")
        assert len(results) == 1

    def test_auto_picks_greedy_for_cross_tier(self, surabaya, kediri_kab, cabai_merah,
                                                  make_supply, make_demand, logistics_normal):
        # Cross-tier (Tier 2 → Tier 1) → harus pakai greedy
        s = make_supply(kediri_kab, cabai_merah)  # Tier 2
        d = make_demand(surabaya, cabai_merah)    # Tier 1
        candidates = [(s, d)]

        def score_fn(s_, d_):
            return compute_score(s_, d_, logistics=logistics_normal)

        results = allocate(candidates, score_fn)
        assert len(results) == 1
        assert results[0].confidence == Confidence.MEDIUM
