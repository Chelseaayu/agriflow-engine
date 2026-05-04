"""
Skenario SPASIAL (B1-B3) — Section 5.5.5 v8 proposal.

B1 — Cross-tier: Tier 1 surplus → Tier 2 deficit, atau sebaliknya
B2 — Long distance: jarak melewati max_distance_km → reject
B3 — Cluster regional surplus (Madura): semua kab cluster surplus → ekspor opp
"""
import pytest

from matching_engine.engine import CLUSTER_MADURA, run_matching


# =============================================================================
# B1 — CROSS-TIER MATCHING
# =============================================================================

class TestB1_CrossTier:
    """Skenario B1: Tier 1 (Kota Kediri) surplus → Tier 2 (Sampang) deficit."""

    def test_tier1_to_tier2_match_marked_medium_confidence(
        self, kota_kediri, sampang, cabai_merah,
        make_supply, make_demand, logistics_normal
    ):
        s = make_supply(kota_kediri, cabai_merah, volume=50, price=30000)
        d = make_demand(sampang, cabai_merah, volume=50, price=55000)

        report = run_matching([s], [d], logistics=logistics_normal)
        assert len(report.matches) == 1
        m = report.matches[0]
        # Cross-tier → MEDIUM confidence
        assert m.confidence.value == "MEDIUM"
        # Tetap dapat equity boost (Sampang IPM 66.72 < 68 → +30%, kalibrasi BPS 2024)
        assert m.equity_multiplier == 1.30
        assert "EQUITY_BOOST_30" in m.flags

    def test_tier2_to_tier1_match_works(
        self, kediri_kab, surabaya, cabai_merah,
        make_supply, make_demand, logistics_normal
    ):
        # Tier 2 surplus → Tier 1 deficit (most common pattern)
        s = make_supply(kediri_kab, cabai_merah, volume=80, price=30000)
        d = make_demand(surabaya, cabai_merah, volume=80, price=60000)

        report = run_matching([s], [d], logistics=logistics_normal)
        assert len(report.matches) == 1
        # Surabaya IPM 84.69 → tidak ada equity boost
        assert report.matches[0].equity_multiplier == 1.00


# =============================================================================
# B2 — LONG DISTANCE REJECTION
# =============================================================================

class TestB2_LongDistance:
    """Skenario B2: Pacitan (barat) ke Banyuwangi (timur) ~400km untuk cabai (max 200km)."""

    def test_distance_exceeds_max_no_match(
        self, pacitan, banyuwangi, cabai_merah,
        make_supply, make_demand, logistics_normal
    ):
        s = make_supply(pacitan, cabai_merah, volume=50, price=30000)
        d = make_demand(banyuwangi, cabai_merah, volume=50, price=60000)

        report = run_matching([s], [d], logistics=logistics_normal)
        # Cabai max_distance=200km, jarak ~400km → reject
        assert len(report.matches) == 0
        assert len(report.unmatched_surplus) == 1
        assert len(report.unmatched_deficit) == 1

    def test_long_distance_ok_for_beras(
        self, pacitan, banyuwangi, beras_premium,
        make_supply, make_demand, logistics_normal
    ):
        # Beras max_distance=800km → 400km masih viable
        s = make_supply(pacitan, beras_premium, volume=100, price=11000)
        d = make_demand(banyuwangi, beras_premium, volume=100, price=15000)

        report = run_matching([s], [d], logistics=logistics_normal)
        assert len(report.matches) == 1


# =============================================================================
# B3 — CLUSTER REGIONAL SURPLUS (MADURA)
# =============================================================================

class TestB3_ClusterMadura:
    """
    Skenario B3: 4 kab Madura semua surplus bawang → cluster.
    Engine harus suggest agregasi & ekspor.
    """

    def test_madura_cluster_creates_external_opportunity(
        self, sampang, bangkalan, pamekasan, sumenep, surabaya, bawang_merah,
        make_supply, make_demand, logistics_normal
    ):
        # Semua 4 kab Madura surplus bawang merah
        s1 = make_supply(sampang, bawang_merah, volume=50, price=25000)
        s2 = make_supply(bangkalan, bawang_merah, volume=60, price=25000)
        s3 = make_supply(pamekasan, bawang_merah, volume=40, price=26000)
        s4 = make_supply(sumenep, bawang_merah, volume=70, price=24000)
        # Sedikit demand di Surabaya
        d = make_demand(surabaya, bawang_merah, volume=30, price=40000)

        report = run_matching([s1, s2, s3, s4], [d], logistics=logistics_normal)
        # External opportunity untuk cluster Madura harus muncul
        assert any("Madura" in opp or "madura" in opp for opp in report.external_opportunities)
        # Match yang terjadi harus di-flag MADURA_CLUSTER
        for m in report.matches:
            if m.surplus.kabupaten.id in CLUSTER_MADURA:
                assert "MADURA_CLUSTER" in m.flags

    def test_cluster_constants_match_section_5_5_5(self):
        """Cluster Madura: 4 kab Bangkalan/Sampang/Pamekasan/Sumenep sesuai v8 5.5.5 B3."""
        assert "3526" in CLUSTER_MADURA  # Bangkalan
        assert "3527" in CLUSTER_MADURA  # Sampang
        assert "3528" in CLUSTER_MADURA  # Pamekasan
        assert "3529" in CLUSTER_MADURA  # Sumenep
        assert len(CLUSTER_MADURA) == 4
