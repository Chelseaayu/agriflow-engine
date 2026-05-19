"""
Tests untuk OSRM road-distance precompute integration.

Precompute matrix di sample_data/road_distance_jatim.csv (1444 pairs untuk
38 kab Jatim). Generated via tools/fetch_osrm_distance.py.

Verifikasi:
  1. Lookup hit untuk pair Jatim yang ada di matrix.
  2. Lookup miss returns None untuk kabupaten yang tidak ada di matrix.
  3. distance_between() prefer road, fallback haversine.
  4. Correctness fix: Kediri->Sumenep cabai (Madura strait detour) DI-REJECT
     di Layer 1 saat pakai road, padahal haversine bilang viable.
"""
import pytest

from matching_engine.constraints import (
    distance_between, haversine_km, is_viable_pair, road_distance_km,
)
from matching_engine.models import (
    Commodity, DemandNode, EmergencyMode, Kabupaten, SupplyNode, Tier,
)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

@pytest.fixture
def cabai_merah():
    """MAX_DISTANCE 200km — yang relevan untuk Madura-detour test."""
    return Commodity(
        code="cabai_merah", nama="Cabai Merah",
        max_distance_km=200, min_viable_tons=1.0, max_fresh_age_days=5,
    )


@pytest.fixture
def kediri():
    return Kabupaten(
        id="3506", nama="Kediri",
        latitude=-7.796, longitude=112.17,
        ipm=74.50, tier=Tier.MEDIUM,
    )


@pytest.fixture
def sumenep():
    """Madura timur — road dari Kediri ~284km karena harus via Suramadu."""
    return Kabupaten(
        id="3529", nama="Sumenep",
        latitude=-7.0067, longitude=113.8525,
        ipm=68.79, tier=Tier.HIGH,
    )


@pytest.fixture
def sampang():
    """Madura barat — road dari Kediri ~198km (just under cabai MAX 200km)."""
    return Kabupaten(
        id="3527", nama="Sampang",
        latitude=-7.1924, longitude=113.2473,
        ipm=66.72, tier=Tier.MEDIUM,
    )


# -----------------------------------------------------------------------------
# 1. Lookup behavior
# -----------------------------------------------------------------------------

class TestRoadDistanceLookup:
    def test_lookup_hit_for_kediri_to_sumenep(self):
        # Confirmed via OSRM /table: Kediri (3506) -> Sumenep (3529) = 283.851km
        d = road_distance_km("3506", "3529")
        assert d is not None
        assert 280 <= d <= 290, f"expected ~284km, got {d}"

    def test_lookup_hit_for_kediri_to_sampang(self):
        # Kediri -> Sampang (via Suramadu) = 197.756km
        d = road_distance_km("3506", "3527")
        assert d is not None
        assert 195 <= d <= 200

    def test_self_loop_returns_zero(self):
        # OSRM reports 0 for self-pair (we include those rows in CSV).
        d = road_distance_km("3506", "3506")
        assert d is not None
        assert d == 0.0

    def test_lookup_miss_returns_none(self):
        # Kab ID di luar Jatim (DKI Jakarta = 3171) — not in matrix.
        d = road_distance_km("3171", "3506")
        assert d is None

    def test_directional_asymmetry_within_tolerance(self):
        # OSRM driving profile bisa asimetris untuk one-way streets, tapi
        # untuk inter-kabupaten Jatim seharusnya sangat dekat.
        ab = road_distance_km("3506", "3527")
        ba = road_distance_km("3527", "3506")
        assert ab is not None and ba is not None
        assert abs(ab - ba) / max(ab, ba) < 0.05, (
            f"directional asymmetry too large: {ab} vs {ba}"
        )


# -----------------------------------------------------------------------------
# 2. distance_between integration (road first, haversine fallback)
# -----------------------------------------------------------------------------

class TestDistanceBetweenPrefersRoad:
    def test_road_used_for_jatim_pair(self, kediri, sumenep, cabai_merah):
        s = SupplyNode(kabupaten=kediri, commodity=cabai_merah,
                       volume_tons=50, price_per_kg=30000)
        d = DemandNode(kabupaten=sumenep, commodity=cabai_merah,
                       volume_tons=50, price_per_kg=55000)
        dist = distance_between(s, d)
        # Haversine ~205km, road ~284km — distance_between harus return road.
        hav = haversine_km(kediri.latitude, kediri.longitude,
                           sumenep.latitude, sumenep.longitude)
        assert dist > hav * 1.3, (
            f"distance_between should prefer road ({dist}) over haversine ({hav})"
        )
        assert 280 <= dist <= 290

    def test_haversine_fallback_for_unknown_kab(self, cabai_merah):
        # Buat dua "kabupaten fiksi" dengan ID di luar Jatim.
        kab_a = Kabupaten(id="9101", nama="Fiktif-A",
                          latitude=-6.0, longitude=106.0, ipm=70, tier=Tier.MEDIUM)
        kab_b = Kabupaten(id="9102", nama="Fiktif-B",
                          latitude=-6.5, longitude=107.0, ipm=70, tier=Tier.MEDIUM)
        s = SupplyNode(kabupaten=kab_a, commodity=cabai_merah,
                       volume_tons=50, price_per_kg=30000)
        d = DemandNode(kabupaten=kab_b, commodity=cabai_merah,
                       volume_tons=50, price_per_kg=55000)
        # Tidak ada di matrix -> fallback haversine.
        expected_hav = haversine_km(-6.0, 106.0, -6.5, 107.0)
        assert distance_between(s, d) == pytest.approx(expected_hav, rel=1e-9)


# -----------------------------------------------------------------------------
# 3. Correctness fix: Madura detour now properly rejected
# -----------------------------------------------------------------------------

class TestMaduraCorrectnessFix:
    """
    Sebelum OSRM precompute: haversine bilang Kediri->Sumenep cabai = ~205km
    -> just over MAX 200km, marginal reject di Layer 1 (atau pass kalau ada
    rounding noise).

    Sebenarnya road via Suramadu = 284km -> jelas-jelas reject. OSRM
    precompute meng-honest-kan engine.
    """

    def test_kediri_to_sumenep_cabai_rejected_at_layer1(
        self, kediri, sumenep, cabai_merah,
    ):
        s = SupplyNode(kabupaten=kediri, commodity=cabai_merah,
                       volume_tons=50, price_per_kg=30000)
        d = DemandNode(kabupaten=sumenep, commodity=cabai_merah,
                       volume_tons=50, price_per_kg=55000)
        ok, reason = is_viable_pair(s, d)
        assert ok is False
        assert reason == "DISTANCE_EXCEEDS_MAX"

    def test_kediri_to_sampang_cabai_still_viable(
        self, kediri, sampang, cabai_merah,
    ):
        # Sampang road 198km < MAX 200km. Tetap viable.
        s = SupplyNode(kabupaten=kediri, commodity=cabai_merah,
                       volume_tons=50, price_per_kg=30000)
        d = DemandNode(kabupaten=sampang, commodity=cabai_merah,
                       volume_tons=50, price_per_kg=55000)
        ok, reason = is_viable_pair(s, d)
        assert ok is True
        assert reason == ""
