"""
AgriFlow Matching Engine — Layer 3 (Equity-Weighted Allocation)
================================================================

Dua strategi allocation berdasarkan tier kabupaten:

    Tier 1 (HIGH confidence) → Modified Gale-Shapley Stable Matching
        - Deficit kab tertinggal proposes first
        - Surplus accept proposal dengan FinalScore tertinggi
        - Stability guarantee (Nobel Prize Economics 2012)

    Tier 2 (MEDIUM confidence) → Greedy Top-K with Equity Priority
        - Sort deficit by equity_multiplier descending
        - Assign each ke top-scored available surplus
        - Honest engineering: data ±15% error → stable matching guarantee
          tidak meaningful, greedy lebih simple & debug-friendly

Cross-tier (Tier 1 surplus dengan Tier 2 deficit, atau sebaliknya):
    Pakai approach Tier 2 (lower complexity respects lower data quality).

Author: AgriFlow Team
Version: 9.0
"""

from __future__ import annotations
from collections import defaultdict
from typing import Callable, Dict, List, Optional, Tuple

# Type alias for an injectable equity policy function.
# Signature: ipm (float) -> multiplier (float).
# The production default is equity_multiplier_value defined below.
EquityFn = Callable[[float], float]

from .models import (
    Confidence, DemandNode, DemandSegment, MatchResult, ScoreBreakdown,
    SupplyNode, Tier,
)


# =============================================================================
# EQUITY MULTIPLIER (Section 5.5.4 Step 3a)
# =============================================================================

def equity_multiplier_value(ipm: float) -> float:
    """
    Equity boost berdasarkan IPM kabupaten — kalibrasi data BPS 2024 Jatim.

    Threshold:
        IPM < 68  → 1.30  (tertinggal severe — Sampang 66.72, Bangkalan 67.70)
        IPM < 72  → 1.15  (tertinggal — Sumenep, Bondowoso, Probolinggo kab,
                            Lumajang, Pamekasan, Situbondo, Pasuruan kab,
                            Pacitan, Jember, Madiun kab)
        IPM < 78  → 1.05  (menengah — Bojonegoro, Banyuwangi, Tulungagung,
                            Malang kab, Magetan, Gresik, Mojokerto, dll)
        IPM ≥ 78  → 1.00  (maju — Sidoarjo, Surabaya, Kota Malang, dll)

    Rasional kalibrasi:
        Threshold lama (<65 → 1.30) tidak pernah ter-trigger dengan data 2024:
        IPM terendah Jatim 2024 = Sampang 66.72. Threshold baru memastikan
        klaim "+30% boost untuk kab tertinggal" konkret applicable ke
        Sampang & Bangkalan (cluster Madura paling tertinggal).
        Sumber IPM: BPS BRS Desember 2024.
    """
    if ipm < 68:
        return 1.30
    elif ipm < 72:
        return 1.15
    elif ipm < 78:
        return 1.05
    else:
        return 1.00


# =============================================================================
# F2 (v11 fix #2) — SEGMENT-AWARE MULTIPLIER
# =============================================================================

# Segment-aware adjustment ranges (kalibrasi konservatif, max swing ±10%
# supaya base_score 5-dim tetap dominan).
#
# HORECA (hotel/restoran/catering): high-volume contract buyers, margin-sensitive.
#   - +5% bonus saat surplus >= 50t (bulk handling efficiency)
#   - -3% penalty saat surplus < 5t (lots of micro-shipments not viable)
#
# GOVERNMENT (Bulog, sekolah, militer): compliance + reliability premium.
#   - +5% bonus saat supplier Tier 1 (HIGH data confidence)
#   - +3% bonus saat harvest_age == 0 (fresh, institutional consumers care)
#
# INDUSTRIAL (pabrik mie/tahu/tempe): raw bulk, processing-grade quality.
#   - +8% bonus saat surplus >= 100t (bulk processing efficiency)
#   - +2% bonus saat supplier Tier 2 (cheaper supply OK untuk processing)
#
# RETAIL (default): no adjustment — baseline.


SEGMENT_BONUS_HORECA_BULK_VOLUME_T = 50.0
SEGMENT_BONUS_INDUSTRIAL_BULK_VOLUME_T = 100.0
SEGMENT_PENALTY_HORECA_MICRO_VOLUME_T = 5.0


def _segment_priority_upper_bound(segment: DemandSegment) -> float:
    """
    Upper-bound multiplier yang achievable untuk segment ini.
    Dipakai oleh greedy allocator untuk sort deficits — segment dengan
    bonus potensial lebih tinggi dapat priority earlier saat supply
    contested. Tidak mengubah final_score, hanya order of processing.
    """
    if segment == DemandSegment.HORECA:
        return 1.05  # best case: bulk bonus
    if segment == DemandSegment.GOVERNMENT:
        return 1.05 * 1.03  # tier1 × fresh = 1.0815
    if segment == DemandSegment.INDUSTRIAL:
        return 1.08 * 1.02  # bulk × tier2-OK = 1.1016
    return 1.00  # RETAIL baseline


def segment_multiplier_value(s: SupplyNode, d: DemandNode) -> tuple[float, list[str]]:
    """
    F2 v11: hitung segment-aware multiplier untuk pair (supply, demand).

    Return (multiplier, applied_flags).
    Multiplier range: [0.97, 1.10]. RETAIL = 1.00 baseline.

    Pure function — tidak modify supply/demand. Multiplier dapat di-audit
    via flag list (HORECA_BULK_BONUS, GOVERNMENT_TIER1_BONUS, dll), supaya
    Pemda/juri dapat trace kenapa segment X menang atas RETAIL.
    """
    mult = 1.00
    flags: list[str] = []

    if d.segment == DemandSegment.RETAIL:
        return mult, flags

    if d.segment == DemandSegment.HORECA:
        if s.volume_tons >= SEGMENT_BONUS_HORECA_BULK_VOLUME_T:
            mult *= 1.05
            flags.append("SEGMENT_HORECA_BULK_BONUS")
        if s.volume_tons < SEGMENT_PENALTY_HORECA_MICRO_VOLUME_T:
            mult *= 0.97
            flags.append("SEGMENT_HORECA_MICRO_PENALTY")

    elif d.segment == DemandSegment.GOVERNMENT:
        if s.kabupaten.is_tier1:
            mult *= 1.05
            flags.append("SEGMENT_GOVERNMENT_TIER1_BONUS")
        if s.harvest_age_days == 0:
            mult *= 1.03
            flags.append("SEGMENT_GOVERNMENT_FRESH_BONUS")

    elif d.segment == DemandSegment.INDUSTRIAL:
        if s.volume_tons >= SEGMENT_BONUS_INDUSTRIAL_BULK_VOLUME_T:
            mult *= 1.08
            flags.append("SEGMENT_INDUSTRIAL_BULK_BONUS")
        if not s.kabupaten.is_tier1:
            # Industrial dapat terima supply Tier 2 (processing-grade) lebih flexibly
            mult *= 1.02
            flags.append("SEGMENT_INDUSTRIAL_TIER2_OK")

    return mult, flags


def determine_confidence(s: SupplyNode, d: DemandNode) -> Confidence:
    """
    Confidence label untuk satu match.
    Both Tier 1 → HIGH
    Cross-tier atau both Tier 2 → MEDIUM
    Kalau ada flag stale data → LOW (di-handle terpisah di engine.py)
    """
    if s.kabupaten.tier == Tier.HIGH and d.kabupaten.tier == Tier.HIGH:
        return Confidence.HIGH
    return Confidence.MEDIUM


# =============================================================================
# TIER 1 — MODIFIED GALE-SHAPLEY STABLE MATCHING
# =============================================================================

def stable_match_tier1(
    candidates: List[Tuple[SupplyNode, DemandNode]],
    score_fn: Callable[[SupplyNode, DemandNode], Tuple[ScoreBreakdown, float, float]],
    *,
    equity_fn: EquityFn = equity_multiplier_value,
) -> List[MatchResult]:
    """
    Modified Gale-Shapley untuk Tier 1.

    Args:
        candidates: pasangan viable dari Layer 1 (semua sudah lolos hard constraint)
        score_fn: fungsi yang return (breakdown, base_score, distance_km)
                  biasanya scoring.compute_score yang sudah di-partial

    Returns:
        List MatchResult — setiap surplus matched dengan satu deficit terbaik.

    Algorithm:
        1. Hitung FinalScore untuk semua candidate
        2. Build preference list per deficit: surplus diranking by FinalScore
        3. Sort deficits by equity_multiplier descending (tertinggal proposes first)
        4. Untuk setiap deficit: propose ke surplus pilihan tertingginya
           - Kalau surplus belum matched → accept
           - Kalau sudah matched dengan deficit X tapi current score > score X → switch
           - Else: deficit lanjut ke pilihan berikutnya

    Time complexity: O(n²) worst case, n = jumlah pair candidate.
    Library reference: pip install matching (game-theoretic algorithms).
    """
    # Step 1: Hitung skor untuk semua candidate
    score_cache: Dict[Tuple[str, str], Tuple[ScoreBreakdown, float, float]] = {}
    final_scores: Dict[Tuple[str, str], float] = {}
    segment_cache: Dict[Tuple[str, str], Tuple[float, list[str]]] = {}

    for s, d in candidates:
        key = (s.kabupaten.id + "_" + s.commodity.code, d.kabupaten.id)
        breakdown, base, dist = score_fn(s, d)
        score_cache[key] = (breakdown, base, dist)
        eq_mult = equity_fn(d.kabupaten.ipm)
        seg_mult, _seg_flags = segment_multiplier_value(s, d)
        segment_cache[key] = (seg_mult, _seg_flags)
        final_scores[key] = base * eq_mult * seg_mult

    # Step 2: Build preference per deficit (surplus diranking by FinalScore desc)
    deficit_prefs: Dict[str, List[Tuple[float, SupplyNode, DemandNode]]] = defaultdict(list)
    for s, d in candidates:
        key = (s.kabupaten.id + "_" + s.commodity.code, d.kabupaten.id)
        deficit_prefs[d.kabupaten.id + "_" + d.commodity.code].append(
            (final_scores[key], s, d)
        )
    for k in deficit_prefs:
        deficit_prefs[k].sort(key=lambda x: -x[0])  # descending

    # Step 3: Sort deficit kabs by equity multiplier descending
    unique_deficits: Dict[str, DemandNode] = {}
    for _s, d in candidates:
        unique_deficits[d.kabupaten.id + "_" + d.commodity.code] = d
    proposers = sorted(
        unique_deficits.items(),
        key=lambda kv: -equity_fn(kv[1].kabupaten.ipm),
    )

    # Step 4: Gale-Shapley iteration
    # surplus_id_commodity → (current_match_deficit, current_final_score)
    surplus_match: Dict[str, Tuple[DemandNode, float]] = {}
    deficit_unmatched: set[str] = {k for k, _ in proposers}

    # Round-robin: setiap deficit yang belum matched coba propose ke pilihan berikutnya
    deficit_proposal_idx: Dict[str, int] = defaultdict(int)
    max_iterations = len(unique_deficits) * 10  # safety

    iteration = 0
    while deficit_unmatched and iteration < max_iterations:
        iteration += 1
        progressed = False
        for d_key, d in list(proposers):
            if d_key not in deficit_unmatched:
                continue
            prefs = deficit_prefs[d_key]
            idx = deficit_proposal_idx[d_key]
            if idx >= len(prefs):
                # exhausted preference list → tetap unmatched
                deficit_unmatched.discard(d_key)
                continue
            score, s, _d = prefs[idx]
            s_key = s.kabupaten.id + "_" + s.commodity.code

            if s_key not in surplus_match:
                # surplus belum matched → accept
                surplus_match[s_key] = (d, score)
                deficit_unmatched.discard(d_key)
                deficit_proposal_idx[d_key] = idx + 1
                progressed = True
            else:
                _existing_d, existing_score = surplus_match[s_key]
                if score > existing_score:
                    # current proposal lebih baik → switch
                    existing_d_key = (
                        _existing_d.kabupaten.id + "_" + _existing_d.commodity.code
                    )
                    surplus_match[s_key] = (d, score)
                    deficit_unmatched.discard(d_key)
                    deficit_unmatched.add(existing_d_key)  # existing kembali ke pool
                    deficit_proposal_idx[d_key] = idx + 1
                    progressed = True
                else:
                    # rejected → coba pilihan berikutnya
                    deficit_proposal_idx[d_key] = idx + 1
                    progressed = True
        if not progressed:
            break

    # Step 5: Build MatchResult
    results: List[MatchResult] = []
    # Re-find original surplus from candidates
    surplus_lookup: Dict[str, SupplyNode] = {}
    for s, _d in candidates:
        surplus_lookup[s.kabupaten.id + "_" + s.commodity.code] = s

    for s_key, (d, fscore) in surplus_match.items():
        s = surplus_lookup[s_key]
        cache_key = (s_key, d.kabupaten.id)
        if cache_key not in score_cache:
            continue
        breakdown, base_score, dist_km = score_cache[cache_key]
        eq_mult = equity_fn(d.kabupaten.ipm)
        seg_mult, seg_flags = segment_cache.get(cache_key, (1.0, []))
        results.append(MatchResult(
            surplus=s, deficit=d,
            matched_volume_tons=min(s.volume_tons, d.volume_tons),
            distance_km=dist_km,
            base_score=base_score,
            equity_multiplier=eq_mult,
            segment_multiplier=seg_mult,
            final_score=fscore,
            confidence=determine_confidence(s, d),
            breakdown=breakdown,
            flags=list(seg_flags),  # segment audit flags
        ))
    # Sort by final_score descending
    results.sort(key=lambda r: -r.final_score)
    return results


# =============================================================================
# TIER 2 — GREEDY TOP-K WITH EQUITY PRIORITY
# =============================================================================

def greedy_match_tier2(
    candidates: List[Tuple[SupplyNode, DemandNode]],
    score_fn: Callable[[SupplyNode, DemandNode], Tuple[ScoreBreakdown, float, float]],
    *,
    equity_fn: EquityFn = equity_multiplier_value,
) -> List[MatchResult]:
    """
    Greedy multi-objective dengan equity priority untuk Tier 2.

    Algorithm:
        1. Group candidate pairs (per komoditas)
        2. Sort deficit by equity_multiplier descending (tertinggal first)
        3. Untuk setiap deficit: pilih top-scored available surplus
        4. Surplus dengan volume <= deficit volume di-remove dari pool
           (1 surplus bisa di-split ke beberapa deficit kalau volume cukup)

    Time complexity: O(n log n).

    Why greedy untuk Tier 2:
        Data ±15% error → stable matching guarantee tidak meaningful.
        Greedy: simpler, debug-friendly, aligns dengan honest engineering.
    """
    # Hitung skor + cache distance
    score_cache: Dict[Tuple[str, str], Tuple[ScoreBreakdown, float, float]] = {}
    for s, d in candidates:
        key = (s.kabupaten.id + "_" + s.commodity.code, d.kabupaten.id)
        if key not in score_cache:
            score_cache[key] = score_fn(s, d)

    # Group candidates by deficit. v11 fix #2: include segment in key so
    # HORECA + RETAIL demands at same (kab, commodity) don't collapse —
    # tiap segment di-allocate independent.
    by_deficit: Dict[str, Tuple[DemandNode, List[SupplyNode]]] = {}
    for s, d in candidates:
        d_key = d.kabupaten.id + "_" + d.commodity.code + "_" + d.segment.value
        if d_key not in by_deficit:
            by_deficit[d_key] = (d, [])
        by_deficit[d_key][1].append(s)

    # Sort deficits by (equity × segment_upper_bound) descending.
    # v11 fix #2: ensures HORECA/INDUSTRIAL/GOVERNMENT get earlier pick at
    # contested supply when their segment bonus would tip them over RETAIL.
    deficits_sorted = sorted(
        by_deficit.items(),
        key=lambda kv: -(
            equity_fn(kv[1][0].kabupaten.ipm)
            * _segment_priority_upper_bound(kv[1][0].segment)
        ),
    )

    # Track remaining volume per surplus (surplus bisa di-split untuk many deficits)
    remaining_volume: Dict[str, float] = {}
    for s, _d in candidates:
        s_key = s.kabupaten.id + "_" + s.commodity.code
        if s_key not in remaining_volume:
            remaining_volume[s_key] = s.volume_tons

    surplus_lookup: Dict[str, SupplyNode] = {}
    for s, _d in candidates:
        surplus_lookup[s.kabupaten.id + "_" + s.commodity.code] = s

    results: List[MatchResult] = []
    for d_key, (d, surpluses) in deficits_sorted:
        # Filter yang masih punya volume
        available = [s for s in surpluses
                     if remaining_volume[s.kabupaten.id + "_" + s.commodity.code] > 0]
        if not available:
            continue

        # Pick best by FinalScore (= base × equity × segment multiplier)
        eq_mult = equity_fn(d.kabupaten.ipm)

        def final_score_for(s: SupplyNode) -> float:
            cache_key = (s.kabupaten.id + "_" + s.commodity.code, d.kabupaten.id)
            _br, base, _dist = score_cache[cache_key]
            seg_mult, _ = segment_multiplier_value(s, d)
            return base * eq_mult * seg_mult

        best_s = max(available, key=final_score_for)
        s_key = best_s.kabupaten.id + "_" + best_s.commodity.code
        cache_key = (s_key, d.kabupaten.id)
        breakdown, base_score, dist_km = score_cache[cache_key]
        seg_mult, seg_flags = segment_multiplier_value(best_s, d)
        final_score = base_score * eq_mult * seg_mult
        matched_vol = min(remaining_volume[s_key], d.volume_tons)

        results.append(MatchResult(
            surplus=best_s, deficit=d,
            matched_volume_tons=matched_vol,
            distance_km=dist_km,
            base_score=base_score,
            equity_multiplier=eq_mult,
            segment_multiplier=seg_mult,
            final_score=final_score,
            confidence=determine_confidence(best_s, d),
            breakdown=breakdown,
            flags=list(seg_flags),  # segment audit flags
        ))
        remaining_volume[s_key] -= matched_vol

    results.sort(key=lambda r: -r.final_score)
    return results


# =============================================================================
# OPTIMAL — CAPACITATED TRANSPORTATION LP (v1.1)
# =============================================================================

LP_STRATEGY_NAMES = {"lp", "optimal", "mcf"}


def lp_optimal_allocate(
    candidates: List[Tuple[SupplyNode, DemandNode]],
    score_fn: Callable[[SupplyNode, DemandNode], Tuple[ScoreBreakdown, float, float]],
    *,
    equity_fn: EquityFn = equity_multiplier_value,
    min_edge_tons: float = 1e-6,
) -> List[MatchResult]:
    """
    Exact optimum of the capacitated transportation problem on the Layer 1
    candidate pool, solved as a linear program with scipy (HiGHS).

        max  sum_e  final_score_e * x_e
        s.t. sum_{e out of supply i}   x_e <= volume_i
             sum_{e into deficit j}    x_e <= volume_j
             0 <= x_e <= min(volume_i, volume_j)

    final_score_e = base_score * equity_multiplier(IPM_j) * segment_multiplier,
    the same objective the greedy allocator ranks by. Putting the equity
    multiplier inside the objective (rather than re-ranking after greedy has
    already committed tonnage) is what closes the welfare gap measured in
    benchmarks/greedy_vs_optimal.py: 11.1% for greedy, 25.4% for the stable
    matcher on the real Jatim pool.

    This is weighted-sum equity, not leximin. A leximin or Gini-penalised
    variant needs sequential LPs and is deliberately out of scope for v1.1.

    Runtime: single-digit milliseconds at provincial scale; the LP is sparse
    (edges <= surplus x top_k) and HiGHS handles the 514-kabupaten pool in
    well under a second.
    """
    if not candidates:
        return []

    try:
        import numpy as np
        from scipy.optimize import linprog
        from scipy.sparse import lil_matrix
    except ImportError as exc:  # pragma: no cover - scipy is pinned in requirements
        raise RuntimeError(
            "lp_optimal_allocate needs scipy (pip install -r requirements.txt)"
        ) from exc

    supply_index: Dict[str, int] = {}
    supply_vol: List[float] = []
    deficit_index: Dict[str, int] = {}
    deficit_vol: List[float] = []
    edges: List[Tuple[int, int, float, SupplyNode, DemandNode, ScoreBreakdown, float, float, float, float, list]] = []
    score_cache: Dict[Tuple[str, str], Tuple[ScoreBreakdown, float, float]] = {}

    for s, d in candidates:
        s_key = s.kabupaten.id + "_" + s.commodity.code
        d_key = d.kabupaten.id + "_" + d.commodity.code + "_" + d.segment.value
        if s_key not in supply_index:
            supply_index[s_key] = len(supply_vol)
            supply_vol.append(s.volume_tons)
        if d_key not in deficit_index:
            deficit_index[d_key] = len(deficit_vol)
            deficit_vol.append(d.volume_tons)
        cache_key = (s_key, d.kabupaten.id + "_" + d.commodity.code + "_" + d.segment.value)
        if cache_key not in score_cache:
            score_cache[cache_key] = score_fn(s, d)
        breakdown, base, dist = score_cache[cache_key]
        eq_mult = equity_fn(d.kabupaten.ipm)
        seg_mult, seg_flags = segment_multiplier_value(s, d)
        fscore = base * eq_mult * seg_mult
        edges.append((
            supply_index[s_key], deficit_index[d_key], fscore,
            s, d, breakdown, base, dist, eq_mult, seg_mult, list(seg_flags),
        ))

    n_e = len(edges)
    n_s = len(supply_vol)
    n_d = len(deficit_vol)

    c = np.array([-e[2] for e in edges], dtype=float)
    bounds = [(0.0, min(e[3].volume_tons, e[4].volume_tons)) for e in edges]
    A = lil_matrix((n_s + n_d, n_e))
    for idx, e in enumerate(edges):
        A[e[0], idx] = 1.0
        A[n_s + e[1], idx] = 1.0
    b = np.array(supply_vol + deficit_vol, dtype=float)

    res = linprog(c, A_ub=A.tocsr(), b_ub=b, bounds=bounds, method="highs")
    if not res.success:
        # Fall back to the shipped greedy allocator rather than fail the run.
        return greedy_match_tier2(candidates, score_fn, equity_fn=equity_fn)

    results: List[MatchResult] = []
    for idx, x in enumerate(res.x):
        if x <= min_edge_tons:
            continue
        _si, _di, fscore, s, d, breakdown, base, dist, eq_mult, seg_mult, seg_flags = edges[idx]
        results.append(MatchResult(
            surplus=s, deficit=d,
            matched_volume_tons=float(x),
            distance_km=dist,
            base_score=base,
            equity_multiplier=eq_mult,
            segment_multiplier=seg_mult,
            final_score=fscore,
            confidence=determine_confidence(s, d),
            breakdown=breakdown,
            flags=list(seg_flags),
        ))
    results.sort(key=lambda r: -r.final_score)
    return results


def welfare(matches: List[MatchResult]) -> float:
    """Equity-weighted welfare: sum of final_score x matched tons."""
    return float(sum(m.final_score * m.matched_volume_tons for m in matches))


# =============================================================================
# DISPATCHER — Pilih algoritma berdasarkan tier composition
# =============================================================================

def allocate(
    candidates: List[Tuple[SupplyNode, DemandNode]],
    score_fn: Callable[[SupplyNode, DemandNode], Tuple[ScoreBreakdown, float, float]],
    force_strategy: Optional[str] = None,
    *,
    equity_fn: EquityFn = equity_multiplier_value,
) -> List[MatchResult]:
    """
    Pilih strategy allocation:
        - Both Tier 1 → stable matching
        - Else → greedy

    Cross-tier handled by greedy (sesuai Section 5.5.4 catatan).

    Args:
        force_strategy: "stable" | "greedy" | "lp" | None
                        "lp" (aliases "optimal", "mcf") solves the exact
                        capacitated transportation optimum, see
                        lp_optimal_allocate. None keeps the v9 auto-detect
                        so golden-number tests stay valid.
        equity_fn: injectable equity policy, ipm -> multiplier.
                   Default: equity_multiplier_value (production step-function).
                   Override only in benchmarks/tests — do not monkeypatch.
    """
    if force_strategy == "stable":
        return stable_match_tier1(candidates, score_fn, equity_fn=equity_fn)
    if force_strategy == "greedy":
        return greedy_match_tier2(candidates, score_fn, equity_fn=equity_fn)
    if force_strategy in LP_STRATEGY_NAMES:
        return lp_optimal_allocate(candidates, score_fn, equity_fn=equity_fn)

    # Auto-detect: kalau semua kab Tier 1 → pakai stable matching
    all_tier1 = all(
        s.kabupaten.is_tier1 and d.kabupaten.is_tier1
        for s, d in candidates
    )
    if all_tier1 and len(candidates) > 0:
        return stable_match_tier1(candidates, score_fn, equity_fn=equity_fn)
    return greedy_match_tier2(candidates, score_fn, equity_fn=equity_fn)
