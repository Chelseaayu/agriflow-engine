"""
AgriFlow Matching Engine — Layer 0 & Layer 1 (Constraints)
===========================================================

Layer 0: Tier classification berdasarkan ID kabupaten.
Layer 1: Hard constraints filtering — semua pair yang tidak lolos langsung di-reject.

Sesuai Section 5.5.4 dari proposal v8/v9.

Author: AgriFlow Team
Version: 9.0
"""

from __future__ import annotations
import math
from datetime import timedelta
from typing import Iterable, List, Set, Tuple

from .models import (
    Commodity, DemandNode, EmergencyMode, Kabupaten,
    LogisticsContext, SupplyNode, Tier,
)


# =============================================================================
# LAYER 0 — TIER CLASSIFICATION
# =============================================================================

# 8 kota IHK Jawa Timur (Section 5.5.3)
TIER_1_KOTA_IHK: Set[str] = {
    "3578",   # Surabaya
    "3573",   # Malang (Kota)
    "3571",   # Kediri (Kota)
    "3577",   # Madiun (Kota)
    "3574",   # Probolinggo (Kota)
    "3510",   # Banyuwangi
    "3529",   # Sumenep
    "3509",   # Jember
}


def determine_tier(kabupaten_id: str) -> Tier:
    """
    Layer 0: Tentukan tier kabupaten dari kode wilayah BPS.

    Latency target: <10ms (lookup di set).
    """
    return Tier.HIGH if kabupaten_id in TIER_1_KOTA_IHK else Tier.MEDIUM


# =============================================================================
# KOMODITAS SPECIFICATIONS (Section 5.5.4 Layer 1 hard constraints)
# =============================================================================

# 19 komoditas Bapanas + tambahan strategis Jatim
COMMODITY_SPECS: dict[str, Commodity] = {
    "cabai_merah": Commodity(
        code="cabai_merah", nama="Cabai Merah Besar",
        max_distance_km=200, min_viable_tons=1.0, max_fresh_age_days=5,
    ),
    "cabai_rawit": Commodity(
        code="cabai_rawit", nama="Cabai Rawit Merah",
        max_distance_km=200, min_viable_tons=1.0, max_fresh_age_days=5,
    ),
    "bawang_merah": Commodity(
        code="bawang_merah", nama="Bawang Merah",
        max_distance_km=400, min_viable_tons=2.0, max_fresh_age_days=30,
    ),
    "bawang_putih": Commodity(
        code="bawang_putih", nama="Bawang Putih (Bonggol)",
        max_distance_km=600, min_viable_tons=2.0, max_fresh_age_days=60,
    ),
    "tomat": Commodity(
        code="tomat", nama="Tomat Sayur",
        max_distance_km=150, min_viable_tons=1.0, max_fresh_age_days=7,
    ),
    "kentang": Commodity(
        code="kentang", nama="Kentang",
        max_distance_km=400, min_viable_tons=2.0, max_fresh_age_days=21,
    ),
    "kol": Commodity(
        code="kol", nama="Kol/Kubis",
        max_distance_km=300, min_viable_tons=2.0, max_fresh_age_days=14,
    ),
    "wortel": Commodity(
        code="wortel", nama="Wortel",
        max_distance_km=300, min_viable_tons=2.0, max_fresh_age_days=14,
    ),
    "beras_premium": Commodity(
        code="beras_premium", nama="Beras Premium",
        max_distance_km=800, min_viable_tons=5.0, max_fresh_age_days=180,
    ),
    "beras_medium": Commodity(
        code="beras_medium", nama="Beras Medium (Bulog)",
        max_distance_km=800, min_viable_tons=5.0, max_fresh_age_days=180,
    ),
    "jagung": Commodity(
        code="jagung", nama="Jagung Pipilan Kering",
        max_distance_km=600, min_viable_tons=5.0, max_fresh_age_days=120,
    ),
    "kedelai": Commodity(
        code="kedelai", nama="Kedelai Lokal",
        max_distance_km=600, min_viable_tons=3.0, max_fresh_age_days=120,
    ),
    "telur_ayam": Commodity(
        code="telur_ayam", nama="Telur Ayam Ras",
        max_distance_km=300, min_viable_tons=1.0, max_fresh_age_days=21,
    ),
    "daging_ayam": Commodity(
        code="daging_ayam", nama="Daging Ayam Ras",
        max_distance_km=200, min_viable_tons=0.5, max_fresh_age_days=3,
    ),
    "daging_sapi": Commodity(
        code="daging_sapi", nama="Daging Sapi Murni",
        max_distance_km=200, min_viable_tons=0.5, max_fresh_age_days=3,
    ),
    "gula_pasir": Commodity(
        code="gula_pasir", nama="Gula Pasir Lokal",
        max_distance_km=600, min_viable_tons=3.0, max_fresh_age_days=365,
    ),
    "minyak_goreng": Commodity(
        code="minyak_goreng", nama="Minyak Goreng Curah",
        max_distance_km=600, min_viable_tons=3.0, max_fresh_age_days=180,
    ),
    "ikan_segar": Commodity(
        code="ikan_segar", nama="Ikan Segar (Bandeng/Tongkol)",
        max_distance_km=150, min_viable_tons=0.5, max_fresh_age_days=2,
    ),
    "tepung_terigu": Commodity(
        code="tepung_terigu", nama="Tepung Terigu",
        max_distance_km=600, min_viable_tons=3.0, max_fresh_age_days=180,
    ),
}


def get_commodity(code: str) -> Commodity:
    """Lookup komoditas dengan error message yang jelas."""
    if code not in COMMODITY_SPECS:
        raise ValueError(
            f"Komoditas tidak dikenali: '{code}'. "
            f"Valid: {sorted(COMMODITY_SPECS.keys())}"
        )
    return COMMODITY_SPECS[code]


# =============================================================================
# DISTANCE CALCULATION
# =============================================================================

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Hitung jarak great-circle dalam km antara 2 koordinat.
    Approximation untuk Layer 1 filtering (cepat, tidak akurat untuk routing).
    Layer 2 nanti pakai Google Maps Routes API untuk jarak jalan real.
    """
    R = 6371.0  # radius bumi km
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def distance_between(s: SupplyNode, d: DemandNode) -> float:
    """Wrapper untuk haversine_km menggunakan SupplyNode/DemandNode."""
    return haversine_km(
        s.kabupaten.latitude, s.kabupaten.longitude,
        d.kabupaten.latitude, d.kabupaten.longitude,
    )


# =============================================================================
# LAYER 1 — HARD CONSTRAINTS
# =============================================================================

class ConstraintReason(str):
    """Alasan kenapa pair di-reject di Layer 1 (untuk debugging/audit)."""
    DIFFERENT_COMMODITY = "DIFFERENT_COMMODITY"
    SUPPLY_BELOW_MIN = "SUPPLY_BELOW_MIN_VIABLE"
    DEMAND_BELOW_MIN = "DEMAND_BELOW_MIN_VIABLE"
    DISTANCE_EXCEEDS_MAX = "DISTANCE_EXCEEDS_MAX"
    SUPPLY_TOO_OLD = "SUPPLY_TOO_OLD_FOR_TRANSIT"
    SAME_KABUPATEN = "SAME_KABUPATEN"
    SUPPLY_UNREACHABLE = "SUPPLY_UNREACHABLE_DISASTER"
    PEMDA_OVERRIDE = "PEMDA_DO_NOT_EXPORT"
    BULOG_RESERVED = "BULOG_PROCUREMENT_PRIORITY"


def is_viable_pair(
    surplus: SupplyNode,
    deficit: DemandNode,
    logistics: LogisticsContext | None = None,
) -> Tuple[bool, str]:
    """
    Layer 1: Cek apakah pair surplus-deficit lolos hard constraints.
    Return (viable, reason). reason kosong jika viable.

    Skenario yang di-cover (Section 5.5.5):
        B2 Long Distance — distance > MAX_DISTANCE → REJECT
        D4 Erupsi — supply UNREACHABLE → REJECT
        D5 Banjir Skala Besar — supply UNREACHABLE → REJECT
        E2 Pemda Override — do_not_export flag → REJECT
        E3 Bulog Priority — bulog_priority flag → REJECT
        A3 Volume Mismatch Drastis — supply >= MIN tetap PASS (di-flag di scoring)
    """
    logistics = logistics or LogisticsContext()

    # Match komoditas
    if surplus.commodity.code != deficit.commodity.code:
        return False, ConstraintReason.DIFFERENT_COMMODITY

    # Hindari self-match
    if surplus.kabupaten.id == deficit.kabupaten.id:
        return False, ConstraintReason.SAME_KABUPATEN

    # Volume minimum (skenario A3)
    spec = surplus.commodity
    if surplus.volume_tons < spec.min_viable_tons:
        return False, ConstraintReason.SUPPLY_BELOW_MIN
    if deficit.volume_tons < spec.min_viable_tons:
        return False, ConstraintReason.DEMAND_BELOW_MIN

    # Skenario D4, D5 — kabupaten unreachable
    if surplus.kabupaten.emergency_mode == EmergencyMode.UNREACHABLE:
        return False, ConstraintReason.SUPPLY_UNREACHABLE
    if deficit.kabupaten.emergency_mode == EmergencyMode.UNREACHABLE:
        return False, ConstraintReason.SUPPLY_UNREACHABLE

    # Skenario E2 — Pemda override
    override_key = f"do_not_export_{spec.code}"
    if surplus.kabupaten.pemda_overrides.get(override_key, False):
        return False, ConstraintReason.PEMDA_OVERRIDE
    if surplus.kabupaten.emergency_mode == EmergencyMode.PEMDA_LOCKED:
        return False, ConstraintReason.PEMDA_OVERRIDE

    # Skenario E3 — Bulog priority (komoditas reserved untuk Bulog procurement)
    # Note: di-handle pula di engine.py untuk allow partial matching pada sisa volume
    if spec.bulog_priority and surplus.kabupaten.id in BULOG_PROCUREMENT_KAB:
        # Akan di-handle di engine.py: reserve 60% volume untuk Bulog,
        # sisanya tetap available. Di sini constraint pass — engine yang split.
        pass

    # Skenario B2 — distance exceeds max
    # Dynamic adjustment untuk skenario E5 (BBM naik → MAX_DISTANCE shrink)
    effective_max_distance = spec.max_distance_km
    if logistics.bbm_change_pct > 0.10:
        # BBM naik >10% → long-haul jadi tidak ekonomis
        effective_max_distance *= (1 - min(0.20, logistics.bbm_change_pct * 0.5))

    distance_km = distance_between(surplus, deficit)
    if distance_km > effective_max_distance:
        return False, ConstraintReason.DISTANCE_EXCEEDS_MAX

    # Perishability — tidak akan sampai segar
    transit_days = math.ceil(
        distance_km / logistics.avg_speed_km_per_hour / logistics.transit_hours_per_day
    )
    if surplus.harvest_age_days + transit_days > spec.max_fresh_age_days:
        return False, ConstraintReason.SUPPLY_TOO_OLD

    return True, ""


# Kab dengan Bulog procurement aktif (skenario E3)
# Update via API Bulog Divre Jatim atau manual dari announcement
BULOG_PROCUREMENT_KAB: Set[str] = set()  # default empty, populated saat runtime


def reset_bulog_procurement():
    """Reset Bulog priority list (untuk testing)."""
    BULOG_PROCUREMENT_KAB.clear()


def set_bulog_procurement(kab_ids: Iterable[str]):
    """Set kabupaten yang sedang ada Bulog procurement aktif."""
    BULOG_PROCUREMENT_KAB.clear()
    BULOG_PROCUREMENT_KAB.update(kab_ids)


# =============================================================================
# LAYER 1 — CANDIDATE GENERATION
# =============================================================================

def generate_candidates(
    surplus_nodes: List[SupplyNode],
    deficit_nodes: List[DemandNode],
    logistics: LogisticsContext | None = None,
    top_k_per_surplus: int = 20,
) -> List[Tuple[SupplyNode, DemandNode]]:
    """
    Layer 1 main entrypoint:
    Filter pasangan viable lalu kerucutkan ke top-K per surplus berdasarkan jarak.

    Args:
        surplus_nodes: list semua kabupaten surplus
        deficit_nodes: list semua kabupaten deficit
        logistics: konteks logistik global (BBM, BBM baseline, dll)
        top_k_per_surplus: maksimum candidate per surplus (default 20)

    Returns:
        List of (surplus, deficit) pairs yang viable, sudah di-prune top-K.

    Latency target: <50ms untuk 38 kab × 19 komoditas (~25k pasangan).
    """
    logistics = logistics or LogisticsContext()

    # Group deficits by commodity untuk efisiensi
    deficits_by_commodity: dict[str, List[DemandNode]] = {}
    for d in deficit_nodes:
        deficits_by_commodity.setdefault(d.commodity.code, []).append(d)

    candidates: List[Tuple[SupplyNode, DemandNode]] = []
    for s in surplus_nodes:
        # cari deficit dengan komoditas sama
        same_commodity_deficits = deficits_by_commodity.get(s.commodity.code, [])

        viable_for_s: List[Tuple[float, DemandNode]] = []
        for d in same_commodity_deficits:
            ok, _reason = is_viable_pair(s, d, logistics)
            if ok:
                dist = distance_between(s, d)
                viable_for_s.append((dist, d))

        # ambil top-K terdekat (proxy untuk priority — Layer 2 yang akan re-rank)
        viable_for_s.sort(key=lambda x: x[0])
        for _dist, d in viable_for_s[:top_k_per_surplus]:
            candidates.append((s, d))

    return candidates
