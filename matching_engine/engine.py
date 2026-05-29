"""
AgriFlow Matching Engine — Main Orchestrator
=============================================

Menggabungkan Layer 0 → 1 → 2 → 3 + handle 19 skenario edge case.

Public entrypoint:
    run_matching(surplus_nodes, deficit_nodes, ...) -> MatchingReport

19 skenario edge case (Section 5.5.5) di-handle di sini melalui:
    - Pre-processing (Layer 0): tier classification, stale data, emergency mode
    - Constraint filtering (Layer 1): hard constraints di constraints.py
    - Score adjustments (Layer 2): weight switching untuk Ramadan/Import policy
    - Post-processing: Bulog priority split, equity tie-break, external opportunities

Author: AgriFlow Team
Version: 9.0
"""

from __future__ import annotations
import time
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional, Set

from . import scoring
from .allocation import allocate, equity_multiplier_value
from .constraints import (
    BULOG_PROCUREMENT_KAB, generate_candidates, is_viable_pair,
)
from .models import (
    Confidence, DemandNode, DemandSegment, EmergencyMode, Kabupaten,
    LogisticsContext, MatchingReport, MatchResult, RouteBlackout,
    SupplyNode, Tier, WeatherForecast,
)


# =============================================================================
# SCENARIO DETECTION (Section 5.5.5)
# =============================================================================

# Threshold untuk anomaly detection
PRICE_ANOMALY_SIGMA = 3.0
SUPPLY_DROP_WOW_THRESHOLD = 0.50    # 50% week-over-week
RAIN_HEAVY_MM = 50.0
RAIN_MEDIUM_MM = 20.0
STALE_DATA_HOURS = 24


def detect_stale_data(
    nodes: List[SupplyNode | DemandNode],
    threshold_hours: float = STALE_DATA_HOURS,
) -> List[SupplyNode | DemandNode]:
    """
    Skenario C3: data > 24 jam dianggap stale.
    Tidak di-drop, tapi di-flag confidence MEDIUM.
    """
    cutoff = datetime.now() - timedelta(hours=threshold_hours)
    stale = [n for n in nodes if n.timestamp < cutoff]
    return stale


def detect_price_anomaly(
    node: SupplyNode | DemandNode,
    historical_median: float,
    historical_std: float,
) -> bool:
    """
    Skenario D3: harga > 3σ dari rolling median dianggap outlier.
    """
    if historical_std == 0:
        return False
    z_score = abs(node.price_per_kg - historical_median) / historical_std
    return z_score > PRICE_ANOMALY_SIGMA


def detect_zero_demand(deficit_nodes: List[DemandNode], commodity_code: str) -> bool:
    """Skenario A4: tidak ada deficit untuk komoditas tertentu."""
    return not any(d.commodity.code == commodity_code for d in deficit_nodes)


def detect_geographic_cluster_surplus(
    surplus_nodes: List[SupplyNode],
    commodity_code: str,
    cluster_kab_ids: Set[str],
) -> bool:
    """
    Skenario B3: regional cluster surplus.
    Misal Madura: Sumenep + Pamekasan + Sampang + Bangkalan semua surplus → cluster.
    """
    in_cluster = [
        s for s in surplus_nodes
        if s.commodity.code == commodity_code
        and s.kabupaten.id in cluster_kab_ids
    ]
    return len(in_cluster) >= max(2, len(cluster_kab_ids) // 2 + 1)


# Cluster definitions (Section 5.5.5 B3 contoh: Madura)
CLUSTER_MADURA: Set[str] = {
    "3526",  # Bangkalan
    "3527",  # Sampang
    "3528",  # Pamekasan
    "3529",  # Sumenep
}


# =============================================================================
# BULOG SPLIT (Skenario E3)
# =============================================================================

BULOG_RESERVE_PCT = 0.60   # 60% reserve untuk Bulog procurement


def apply_bulog_split(
    surplus_nodes: List[SupplyNode],
    bulog_procurement_kab: Optional[Set[str]] = None,
) -> tuple[List[SupplyNode], List[str]]:
    """
    Skenario E3 Bulog Priority:
    Untuk surplus di kab procurement aktif, reserve 60% volume untuk Bulog,
    sisanya available untuk private matching.

    Args:
        surplus_nodes: list of supply nodes
        bulog_procurement_kab: explicit set of kab IDs with active Bulog
            procurement. Eksplisit > implicit — kalau None, fallback ke
            module global BULOG_PROCUREMENT_KAB (untuk back-compat dengan
            set_bulog_procurement()). Caller paralel HARUS pass eksplisit
            untuk hindari race pada global.

    Return (adjusted_surplus_nodes, warning_messages).
    """
    active_kab = (
        bulog_procurement_kab if bulog_procurement_kab is not None
        else BULOG_PROCUREMENT_KAB
    )
    adjusted = []
    warnings = []
    for s in surplus_nodes:
        if (s.commodity.code in {"beras_premium", "beras_medium", "jagung", "kedelai"}
                and s.kabupaten.id in active_kab):
            reserved = s.volume_tons * BULOG_RESERVE_PCT
            available = s.volume_tons - reserved
            if available <= 0:
                warnings.append(
                    f"{s.kabupaten.nama} {s.commodity.nama}: "
                    f"100% reserved untuk Bulog procurement ({s.volume_tons}t)"
                )
                continue
            new_s = SupplyNode(
                kabupaten=s.kabupaten,
                commodity=s.commodity,
                volume_tons=available,
                price_per_kg=s.price_per_kg,
                harvest_age_days=s.harvest_age_days,
                timestamp=s.timestamp,
                data_source=s.data_source,
            )
            adjusted.append(new_s)
            warnings.append(
                f"{s.kabupaten.nama} {s.commodity.nama}: "
                f"{reserved:.1f}t Bulog priority, {available:.1f}t available"
            )
        else:
            adjusted.append(s)
    return adjusted, warnings


# =============================================================================
# RAMADAN ADJUSTMENT (Skenario C1)
# =============================================================================

def is_ramadan_proximity(reference_date: Optional[datetime] = None) -> bool:
    """
    Skenario C1: H-14 sebelum Idul Fitri.
    Production: integrasi Hijri calendar API (Aladhan).
    Fallback: hardcoded date untuk year terkini.

    Catatan tim: ganti tanggal di bawah setiap tahun atau pakai
    `data_sources.hijri_calendar.is_ramadan_period()`.
    """
    reference_date = reference_date or datetime.now()

    # Idul Fitri 2026: 20 Maret (kasar) — H-14 = 6 Maret 2026
    idul_fitri_2026 = datetime(2026, 3, 20)
    spike_window_start = idul_fitri_2026 - timedelta(days=21)
    spike_window_end = idul_fitri_2026 - timedelta(days=1)
    if spike_window_start <= reference_date <= spike_window_end:
        return True

    # Idul Fitri 2027: ~9 Maret 2027
    idul_fitri_2027 = datetime(2027, 3, 9)
    spike_window_start = idul_fitri_2027 - timedelta(days=21)
    spike_window_end = idul_fitri_2027 - timedelta(days=1)
    if spike_window_start <= reference_date <= spike_window_end:
        return True
    return False


# =============================================================================
# C4 — HOLIDAY CALENDAR (extends C1 Ramadan to multi-event)
# =============================================================================

def get_active_demand_event(
    reference_date: Optional[datetime] = None,
) -> Optional[str]:
    """
    Skenario C4: deteksi event demand spike yang sedang aktif.

    Return event name: "RAMADAN" | "IMLEK" | "NATAL" | "SCHOOL_START" | None.

    Window per event:
        RAMADAN — H-21 to H-1 sebelum Idul Fitri (warisan dari C1)
        IMLEK   — H-7 to H-1 sebelum Chinese New Year (window pendek)
        NATAL   — H-21 to H-1 sebelum 25 Desember
        SCHOOL_START — 2 minggu sebelum mid-Juli + mid-Januari (kos-kosan)

    Priority order saat overlap: RAMADAN > NATAL > IMLEK > SCHOOL_START.
    Production: ganti hardcoded tanggal dengan Hijri + Lunar calendar API.
    """
    reference_date = reference_date or datetime.now()
    yr = reference_date.year

    # RAMADAN — re-use existing logic
    if is_ramadan_proximity(reference_date):
        return "RAMADAN"

    # NATAL — H-21 to H-1
    for natal_yr in (yr, yr - 1, yr + 1):
        natal = datetime(natal_yr, 12, 25)
        if natal - timedelta(days=21) <= reference_date <= natal - timedelta(days=1):
            return "NATAL"

    # IMLEK — hardcoded approximations (production: lunar calendar)
    imlek_dates = {
        2026: datetime(2026, 2, 17),
        2027: datetime(2027, 2, 6),
        2028: datetime(2028, 1, 26),
    }
    imlek = imlek_dates.get(yr) or imlek_dates.get(yr - 1)
    if imlek:
        if imlek - timedelta(days=7) <= reference_date <= imlek - timedelta(days=1):
            return "IMLEK"

    # SCHOOL_START — 2 minggu sebelum mid-Juli & mid-Januari
    for school_start in (datetime(yr, 7, 15), datetime(yr, 1, 15)):
        if school_start - timedelta(days=14) <= reference_date <= school_start:
            return "SCHOOL_START"

    return None


def _weights_for_event(event: Optional[str]) -> Dict[str, float]:
    """Map event name → weight profile dari scoring.py."""
    if event == "RAMADAN":
        return scoring.RAMADAN_WEIGHTS
    if event == "IMLEK":
        return scoring.IMLEK_WEIGHTS
    if event == "NATAL":
        return scoring.NATAL_WEIGHTS
    if event == "SCHOOL_START":
        return scoring.SCHOOL_START_WEIGHTS
    return scoring.DEFAULT_WEIGHTS


# =============================================================================
# D6 — ROUTE BLACKOUT (mudik / demonstrasi / maintenance)
# =============================================================================

def is_route_blacked_out(
    origin_id: str,
    dest_id: str,
    blackouts: List[RouteBlackout],
    reference_date: datetime,
) -> Optional[RouteBlackout]:
    """
    Skenario D6: cek apakah rute origin→dest sedang ditutup pada reference_date.
    Return RouteBlackout pertama yang matching, None kalau bersih.
    Wildcard "*" pada origin/dest cocok semua kab.
    """
    for b in blackouts:
        if b.is_active(reference_date) and b.matches_route(origin_id, dest_id):
            return b
    return None


# =============================================================================
# E6 — CONTRACT RESERVE (generalized Bulog pattern)
# =============================================================================

def apply_contract_reserve(
    surplus_nodes: List[SupplyNode],
    contracts: Optional[Dict[tuple, float]] = None,
) -> tuple[List[SupplyNode], List[str]]:
    """
    Skenario E6: generalisasi Bulog reserve pattern untuk contract farming
    pre-commitment (mis. Carrefour MoU 70%, Indofood kontrak gula 50%).

    Args:
        contracts: Dict[(kab_id, commodity_code), reserve_pct_0_to_1]
            mis. {("3506", "bawang_merah"): 0.70} → 70% bawang Kediri
            reserved untuk kontrak, 30% available untuk spot matching.

    Return (adjusted_surplus_nodes, warning_messages).
    """
    if not contracts:
        return list(surplus_nodes), []
    adjusted = []
    warnings = []
    for s in surplus_nodes:
        key = (s.kabupaten.id, s.commodity.code)
        reserve_pct = contracts.get(key)
        if reserve_pct is None or reserve_pct <= 0:
            adjusted.append(s)
            continue
        reserved = s.volume_tons * reserve_pct
        available = s.volume_tons - reserved
        if available <= 0:
            warnings.append(
                f"{s.kabupaten.nama} {s.commodity.nama}: "
                f"100% reserved untuk contract ({s.volume_tons:.1f}t)"
            )
            continue
        new_s = SupplyNode(
            kabupaten=s.kabupaten,
            commodity=s.commodity,
            volume_tons=available,
            price_per_kg=s.price_per_kg,
            harvest_age_days=s.harvest_age_days,
            timestamp=s.timestamp,
            data_source=s.data_source,
        )
        adjusted.append(new_s)
        warnings.append(
            f"{s.kabupaten.nama} {s.commodity.nama}: "
            f"{reserved:.1f}t contract priority ({reserve_pct*100:.0f}%), "
            f"{available:.1f}t available untuk spot matching"
        )
    return adjusted, warnings


# =============================================================================
# MAIN ENTRYPOINT
# =============================================================================

def run_matching(
    surplus_nodes: List[SupplyNode],
    deficit_nodes: List[DemandNode],
    logistics: Optional[LogisticsContext] = None,
    weather_forecasts: Optional[Dict[str, WeatherForecast]] = None,
    historical_prices: Optional[Dict[str, tuple[float, float]]] = None,
    # historical_prices: {commodity_code: (median, std)} untuk anomaly detection
    import_policy_active: bool = False,
    reference_date: Optional[datetime] = None,
    force_strategy: Optional[str] = None,
    route_blackouts: Optional[List[RouteBlackout]] = None,
    contracts: Optional[Dict[tuple, float]] = None,
    allow_grade_substitution: bool = False,
    bulog_procurement_kab: Optional[Set[str]] = None,
    equity_fn: Optional[Callable[[float], float]] = None,
) -> MatchingReport:
    """
    AgriFlow Matching Engine — main entrypoint.

    Args:
        surplus_nodes: list semua kabupaten surplus untuk semua komoditas hari itu
        deficit_nodes: list semua kabupaten deficit
        logistics: konteks logistik global (BBM, BBM baseline)
        weather_forecasts: dict (origin_id + dest_id) → WeatherForecast
        historical_prices: dict commodity_code → (median, std) 30-day rolling
        import_policy_active: skenario E4 — bobot price diturunkan
        reference_date: untuk Ramadan detection (default: now)
        force_strategy: "stable" | "greedy" untuk testing override
        bulog_procurement_kab: set of kab IDs dengan Bulog procurement aktif
            untuk run ini. Pass eksplisit kalau memanggil run_matching secara
            paralel (mis. FastAPI multi-worker) supaya tidak race pada module
            global. None → fallback ke BULOG_PROCUREMENT_KAB module-level
            (di-set via set_bulog_procurement, back-compat untuk tests).

    Returns:
        MatchingReport dengan matches, unmatched, warnings, metadata.

    Latency target: <500ms p99 untuk 38 kab × 19 komoditas (Section 5.5.4).
    """
    t_start = time.perf_counter()
    warnings: List[str] = []
    external_opportunities: List[str] = []

    logistics = logistics or LogisticsContext()
    weather_forecasts = weather_forecasts or {}
    historical_prices = historical_prices or {}

    # =========================================================================
    # PRE-PROCESSING
    # =========================================================================

    # Skenario C3 — stale data detection
    stale_supply = detect_stale_data(surplus_nodes)
    stale_demand = detect_stale_data(deficit_nodes)
    # Build lookup set untuk identitas stable (kab_id + commodity_code) —
    # menggunakan `in` operator pada list dataclass instance fragile karena
    # bergantung pada object identity / __eq__ behavior.
    stale_supply_keys = {(n.kabupaten.id, n.commodity.code) for n in stale_supply}
    stale_demand_keys = {(n.kabupaten.id, n.commodity.code) for n in stale_demand}
    if stale_supply or stale_demand:
        warnings.append(
            f"Stale data detected: {len(stale_supply)} supply, "
            f"{len(stale_demand)} demand nodes >24h. Confidence downgraded."
        )

    # Skenario D3 — price anomaly: drop dari pool
    if historical_prices:
        clean_supply = []
        for s in surplus_nodes:
            stats = historical_prices.get(s.commodity.code)
            if stats and detect_price_anomaly(s, stats[0], stats[1]):
                warnings.append(
                    f"Price anomaly detected: {s.kabupaten.nama} {s.commodity.nama} "
                    f"@ Rp {s.price_per_kg:,.0f}/kg (median Rp {stats[0]:,.0f}). "
                    f"Excluded — manual review pending."
                )
                continue
            clean_supply.append(s)
        surplus_nodes = clean_supply

        clean_demand = []
        for d in deficit_nodes:
            stats = historical_prices.get(d.commodity.code)
            if stats and detect_price_anomaly(d, stats[0], stats[1]):
                warnings.append(
                    f"Price anomaly detected: {d.kabupaten.nama} {d.commodity.nama} "
                    f"@ Rp {d.price_per_kg:,.0f}/kg. Excluded."
                )
                continue
            clean_demand.append(d)
        deficit_nodes = clean_demand

    # Skenario E3 — Bulog procurement split
    surplus_nodes, bulog_warnings = apply_bulog_split(
        surplus_nodes, bulog_procurement_kab=bulog_procurement_kab
    )
    warnings.extend(bulog_warnings)

    # Skenario E6 — Contract reserve (generalisasi Bulog untuk MoU swasta)
    surplus_nodes, contract_warnings = apply_contract_reserve(surplus_nodes, contracts)
    warnings.extend(contract_warnings)

    # Skenario C1 + C4 — Holiday calendar (RAMADAN / IMLEK / NATAL / SCHOOL_START)
    active_event = get_active_demand_event(reference_date)
    if logistics.is_ramadan_proximity:
        active_event = active_event or "RAMADAN"
    ramadan_active = active_event == "RAMADAN"
    if active_event:
        weights = _weights_for_event(active_event)
        event_label = {
            "RAMADAN": "Pre-Ramadan/Idul Fitri",
            "IMLEK": "Pre-Imlek",
            "NATAL": "Pre-Natal",
            "SCHOOL_START": "School-start kos-kosan",
        }.get(active_event, active_event)
        warnings.append(f"{event_label} spike mode aktif — "
                        f"bobot scoring disesuaikan untuk event ini.")
    elif import_policy_active:
        weights = scoring.IMPORT_POLICY_WEIGHTS
        warnings.append("Import policy detected — bobot price diturunkan, "
                        "matching deprioritized untuk komoditas terdampak.")
    else:
        weights = scoring.DEFAULT_WEIGHTS

    # Skenario A4 — zero demand check per komoditas
    surplus_commodities = {s.commodity.code for s in surplus_nodes}
    for comm_code in surplus_commodities:
        if detect_zero_demand(deficit_nodes, comm_code):
            external_opportunities.append(
                f"{comm_code}: tidak ada internal demand. "
                f"Saran: ekspor luar Jatim (Jakarta/Bali) atau Bulog procurement."
            )

    # Skenario B3 — geographic cluster surplus (Madura)
    for comm_code in surplus_commodities:
        if detect_geographic_cluster_surplus(surplus_nodes, comm_code, CLUSTER_MADURA):
            cluster_supply = sum(
                s.volume_tons for s in surplus_nodes
                if s.commodity.code == comm_code and s.kabupaten.id in CLUSTER_MADURA
            )
            external_opportunities.append(
                f"Cluster Madura surplus {comm_code}: {cluster_supply:.0f}t total. "
                f"Saran: agregasi ekspor ke Surabaya/Sidoarjo via Suramadu."
            )

    # =========================================================================
    # LAYER 1 — CANDIDATE GENERATION
    # =========================================================================
    candidates = generate_candidates(
        surplus_nodes, deficit_nodes, logistics=logistics,
        allow_grade_substitution=allow_grade_substitution,
    )

    # Skenario D6 — Filter rute yang ditutup (mudik / demo / maintenance)
    if route_blackouts:
        ref_date = reference_date or datetime.now()
        filtered = []
        blackout_count = 0
        for s, d in candidates:
            blocked = is_route_blacked_out(
                s.kabupaten.id, d.kabupaten.id, route_blackouts, ref_date,
            )
            if blocked:
                blackout_count += 1
                continue
            filtered.append((s, d))
        if blackout_count > 0:
            warnings.append(
                f"Route blackout aktif: {blackout_count} pair difilter karena "
                f"rute tertutup pada {ref_date.date().isoformat()}."
            )
        candidates = filtered

    # Track unmatched surplus/deficit
    matched_surplus_ids: Set[str] = set()
    matched_deficit_ids: Set[str] = set()

    if not candidates:
        latency_ms = (time.perf_counter() - t_start) * 1000
        return MatchingReport(
            matches=[],
            unmatched_surplus=list(surplus_nodes),
            unmatched_deficit=list(deficit_nodes),
            external_opportunities=external_opportunities,
            warnings=warnings + ["Tidak ada candidate pair yang lolos hard constraints."],
            run_metadata={
                "latency_ms": round(latency_ms, 2),
                "tier1_candidates": 0,
                "tier2_candidates": 0,
                "weights_used": weights,
            },
        )

    # =========================================================================
    # LAYER 2 — SCORING (closure menangkap weights, logistics, weather)
    # =========================================================================
    def score_fn(s: SupplyNode, d: DemandNode):
        # Lookup weather forecast untuk rute
        wf_key = f"{s.kabupaten.id}_{d.kabupaten.id}"
        wf = weather_forecasts.get(wf_key)
        return scoring.compute_score(
            s, d, logistics=logistics, weather=wf, weights=weights
        )

    # =========================================================================
    # LAYER 3 — ALLOCATION
    # =========================================================================
    _equity_fn = equity_fn if equity_fn is not None else equity_multiplier_value
    matches = allocate(candidates, score_fn=score_fn, force_strategy=force_strategy,
                       equity_fn=_equity_fn)

    # =========================================================================
    # POST-PROCESSING
    # =========================================================================

    # Tag flags untuk tracking. v11: preserve segment flags from allocation
    # (F2 segment-aware multiplier emits audit flags like SEGMENT_HORECA_BULK_BONUS).
    for m in matches:
        flags = list(m.flags) if m.flags else []  # preserve segment audit flags
        if ramadan_active:
            flags.append("RAMADAN_SPIKE")
        elif active_event == "IMLEK":
            flags.append("IMLEK_SPIKE")
        elif active_event == "NATAL":
            flags.append("NATAL_SPIKE")
        elif active_event == "SCHOOL_START":
            flags.append("SCHOOL_START_SPIKE")
        if import_policy_active:
            flags.append("IMPORT_POLICY_ACTIVE")
        if m.equity_multiplier == 1.30:
            flags.append("EQUITY_BOOST_30")
        elif m.equity_multiplier == 1.15:
            flags.append("EQUITY_BOOST_15")
        elif m.equity_multiplier == 1.05:
            flags.append("EQUITY_BOOST_05")
        if (m.surplus.kabupaten.id in CLUSTER_MADURA
                or m.deficit.kabupaten.id in CLUSTER_MADURA):
            flags.append("MADURA_CLUSTER")
        if m.deficit.kabupaten.emergency_mode == EmergencyMode.HUMANITARIAN:
            flags.append("HUMANITARIAN_PRIORITY")
        # F1 — Grade substitution flag
        if m.surplus.commodity.code != m.deficit.commodity.code:
            flags.append("GRADE_SUBSTITUTION")
            m.notes = (
                f"{m.surplus.commodity.code} digunakan untuk memenuhi demand "
                f"{m.deficit.commodity.code} (grade compatible substitution)."
            )
        # F2 — Demand segmentation flag (non-default segment)
        if m.deficit.segment != DemandSegment.RETAIL:
            flags.append(f"SEGMENT_{m.deficit.segment.value}")
        # Stale data flag → confidence drop satu tingkat
        # HIGH → MEDIUM, MEDIUM → LOW (sesuai spec C3).
        s_key = (m.surplus.kabupaten.id, m.surplus.commodity.code)
        d_key = (m.deficit.kabupaten.id, m.deficit.commodity.code)
        if s_key in stale_supply_keys or d_key in stale_demand_keys:
            flags.append("STALE_DATA_24H")
            if m.confidence == Confidence.HIGH:
                m.confidence = Confidence.MEDIUM
            elif m.confidence == Confidence.MEDIUM:
                m.confidence = Confidence.LOW
        # Skenario A3 — volume mismatch drastis
        ratio = min(m.surplus.volume_tons, m.deficit.volume_tons) / max(
            m.surplus.volume_tons, m.deficit.volume_tons
        )
        if ratio < 0.20:
            flags.append("VOLUME_MISMATCH_DRASTIS")
            m.notes = ("Marginal contribution: surplus/demand ratio < 20%. "
                       "Suggest combine dengan source lain.")
        m.flags = flags
        matched_surplus_ids.add(m.surplus.kabupaten.id + "_" + m.surplus.commodity.code)
        matched_deficit_ids.add(m.deficit.kabupaten.id + "_" + m.deficit.commodity.code)

    # Identifikasi unmatched
    unmatched_surplus = [
        s for s in surplus_nodes
        if (s.kabupaten.id + "_" + s.commodity.code) not in matched_surplus_ids
    ]
    unmatched_deficit = [
        d for d in deficit_nodes
        if (d.kabupaten.id + "_" + d.commodity.code) not in matched_deficit_ids
    ]

    latency_ms = (time.perf_counter() - t_start) * 1000

    tier1_count = sum(
        1 for m in matches
        if m.surplus.kabupaten.is_tier1 and m.deficit.kabupaten.is_tier1
    )

    return MatchingReport(
        matches=matches,
        unmatched_surplus=unmatched_surplus,
        unmatched_deficit=unmatched_deficit,
        external_opportunities=external_opportunities,
        warnings=warnings,
        run_metadata={
            "latency_ms": round(latency_ms, 2),
            "total_matches": len(matches),
            "tier1_tier1_matches": tier1_count,
            "cross_or_tier2_matches": len(matches) - tier1_count,
            "candidate_pairs_evaluated": len(candidates),
            "weights_used": weights,
            "ramadan_active": ramadan_active,
            "import_policy_active": import_policy_active,
            "bbm_change_pct": logistics.bbm_change_pct,
            "stale_data_count": len(stale_supply) + len(stale_demand),
        },
    )
