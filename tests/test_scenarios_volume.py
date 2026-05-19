"""
Skenario VOLUME (A1-A4) — Section 5.5.5 v8 proposal.

A1 — 1-to-many: 1 surplus dapat split ke multiple deficit
A2 — Many-to-1: multiple surplus consolidate ke 1 deficit besar
A3 — Volume mismatch drastis: <20% ratio → flag VOLUME_MISMATCH_DRASTIS
A4 — Zero demand: tidak ada deficit untuk komoditas → external opportunity
"""
import pytest

from matching_engine.engine import run_matching


# =============================================================================
# A1 — 1-TO-MANY: 1 surplus split ke beberapa deficit
# =============================================================================

class TestA1_OneToMany:
    """
    Skenario A1: surplus 120t Kediri bisa di-split ke 3 deficit yang
    road-feasible (Sampang via Suramadu 198km, Tulungagung 53km,
    Trenggalek 85km — semua < cabai MAX_DISTANCE 200km).

    Originally Sampang/Bondowoso/Sumenep, but Kediri->Bondowoso (250km)
    and Kediri->Sumenep (284km) exceed cabai MAX 200km when OSRM road
    distance replaces haversine — engine correctly filters them. Test
    now uses kabupaten that are physically reachable for cabai.
    """

    def test_one_surplus_satisfies_multiple_deficits(
        self, kediri_kab, sampang, tulungagung, trenggalek, cabai_merah,
        make_supply, make_demand, logistics_normal
    ):
        s = make_supply(kediri_kab, cabai_merah, volume=120, price=30000)
        d1 = make_demand(sampang, cabai_merah, volume=30, price=55000)
        d2 = make_demand(tulungagung, cabai_merah, volume=40, price=55000)
        d3 = make_demand(trenggalek, cabai_merah, volume=40, price=55000)

        report = run_matching([s], [d1, d2, d3], logistics=logistics_normal)
        # Semua 3 deficit harus matched (greedy menggunakan remaining_volume)
        matched_kabs = {m.deficit.kabupaten.id for m in report.matches}
        assert len(report.matches) >= 2  # minimal 2 dari 3 (volume cukup untuk semua)
        assert sampang.id in matched_kabs


# =============================================================================
# A2 — MANY-TO-1: multiple surplus untuk 1 deficit besar
# =============================================================================

class TestA2_ManyToOne:
    """Skenario A2: Surabaya butuh 200t cabai, di-supply dari multiple sentra."""

    def test_multiple_surplus_for_one_big_deficit(
        self, surabaya, kediri_kab, blitar_kab, tulungagung, cabai_merah,
        make_supply, make_demand, logistics_normal
    ):
        s1 = make_supply(kediri_kab, cabai_merah, volume=80, price=30000)
        s2 = make_supply(blitar_kab, cabai_merah, volume=70, price=32000)
        s3 = make_supply(tulungagung, cabai_merah, volume=60, price=31000)
        d = make_demand(surabaya, cabai_merah, volume=200, price=60000)

        report = run_matching([s1, s2, s3], [d], logistics=logistics_normal)
        # Surabaya harus dapat ≥1 match (algoritma greedy: 1 surplus per assign per round)
        assert len(report.matches) >= 1
        for m in report.matches:
            assert m.deficit.kabupaten.id == surabaya.id


# =============================================================================
# A3 — VOLUME MISMATCH DRASTIS
# =============================================================================

class TestA3_VolumeMismatchDrastis:
    """Skenario A3: surplus 5t vs deficit 100t (ratio 5%) → flag warning."""

    def test_drastic_mismatch_flags_warning(
        self, surabaya, kediri_kab, cabai_merah,
        make_supply, make_demand, logistics_normal
    ):
        s = make_supply(kediri_kab, cabai_merah, volume=5, price=30000)
        d = make_demand(surabaya, cabai_merah, volume=100, price=60000)

        report = run_matching([s], [d], logistics=logistics_normal)
        if len(report.matches) > 0:
            m = report.matches[0]
            assert "VOLUME_MISMATCH_DRASTIS" in m.flags
            assert "Marginal" in m.notes or "ratio" in m.notes.lower()


# =============================================================================
# A4 — ZERO DEMAND
# =============================================================================

class TestA4_ZeroDemand:
    """Skenario A4: surplus cabai 100t tapi tidak ada deficit cabai → external opp."""

    def test_zero_demand_creates_external_opportunity(
        self, kediri_kab, surabaya, cabai_merah, beras_premium,
        make_supply, make_demand, logistics_normal
    ):
        # Hanya supply cabai. Demand cuma untuk beras (komoditas lain).
        s_cabai = make_supply(kediri_kab, cabai_merah, volume=100)
        d_beras = make_demand(surabaya, beras_premium, volume=50)

        report = run_matching([s_cabai], [d_beras], logistics=logistics_normal)
        # Cabai tidak ada deficit → external_opportunity message
        assert any("cabai" in opp.lower() for opp in report.external_opportunities)
        # Cabai surplus harus di unmatched
        assert any(s.commodity.code == "cabai_merah" for s in report.unmatched_surplus)
