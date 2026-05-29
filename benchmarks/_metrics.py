"""
benchmarks/_metrics.py — Pure equity metrics helpers.

No engine imports. All functions are pure (no side effects, no I/O).
These are the five metrics columns in the baseline comparison table.

Metric definitions
------------------
total_deficit_covered
    Volume-weighted coverage: sum of min(matched, demanded) across all
    (kab, commodity, segment) keys divided by total demand volume.
    This is tons fulfilled / tons demanded, NOT count of kab covered.
    A 200-ton deficit that is 50% filled counts more than a 10-ton
    deficit that is 100% filled.

gini
    Weighted Gini coefficient from the Lorenz curve formulation:

        G = Σᵢ Σⱼ wᵢ wⱼ |rᵢ − rⱼ| / (2 (Σwᵢ)² r̄)

    where:
        rᵢ  = fulfillment ratio for node i (matched_tons / demand_tons)
        wᵢ  = demand volume weight (demand_tons for node i)
        r̄   = weighted mean fulfillment ratio

    Verification invariants:
        gini_weighted([1,1,1,1], equal weights) ≈ 0.0   (perfectly equal)
        gini_weighted([1,0,0,0], equal weights) > 0.6    (maximum inequality)
        uniform allocation  → Gini ≈ 0 (everyone gets same ratio)
        pure greedy         → Gini highest (best nodes get everything first)

atkinson
    Atkinson index A(ε) = 1 − (1/μ) * (Σᵢ wᵢ rᵢ^(1−ε) / Σᵢ wᵢ)^(1/(1−ε))
    for ε ≠ 1.  For ε = 1: A(1) = 1 − exp(Σᵢ wᵢ ln(rᵢ) / Σᵢ wᵢ) / μ.
    Reported at ε=0.5 (moderate inequality aversion) and ε=1.0 (strong).
    wᵢ = demand_tons weight.  rᵢ values of 0 handled by clamping to 1e-9
    before log, consistent with standard practice.

min_fulfillment
    Leximin gap = the single worst fulfillment ratio across all nodes.
    One number per strategy; higher is better.

kab_fulfillment
    Volume-weighted fulfillment ratio for a single kabupaten across all
    its (commodity, segment) demand nodes.
    Used for Sampang (3527) and Bangkalan (3526) headline numbers.
"""
from __future__ import annotations

import math
from typing import Dict, Tuple


# Key type used throughout: (kab_id, commodity_code, segment_value) -> float
_Key = Tuple[str, str, str]


def fulfillment_by_node(
    matched_tons: Dict[_Key, float],
    demand_tons: Dict[_Key, float],
) -> Dict[_Key, float]:
    """
    Per-node fulfillment ratio capped at 1.0.

    Args:
        matched_tons: dict key -> tons matched (may be missing for unmatched nodes)
        demand_tons:  dict key -> tons demanded (positive values only)

    Returns:
        dict key -> ratio in [0.0, 1.0] for every key with demand_tons > 0.
    """
    return {
        k: min(1.0, matched_tons.get(k, 0.0) / v)
        for k, v in demand_tons.items()
        if v > 0
    }


def total_deficit_covered(
    matched_tons: Dict[_Key, float],
    demand_tons: Dict[_Key, float],
) -> float:
    """
    Volume-weighted coverage ratio: tons fulfilled / tons demanded.

    This is NOT a count of kabupaten covered — it weights each node by
    its demand volume so a 200-ton deficit that is half-filled (100t)
    contributes more than a 10-ton deficit that is fully filled (10t).

    Returns a float in [0.0, 1.0].
    """
    total = sum(demand_tons.values())
    if total == 0:
        return 0.0
    covered = sum(
        min(matched_tons.get(k, 0.0), v) for k, v in demand_tons.items()
    )
    return covered / total


def gini(
    matched_tons: Dict[_Key, float],
    demand_tons: Dict[_Key, float],
) -> float:
    """
    Weighted Gini from the Lorenz curve mean-absolute-difference formula.

        G = Σᵢ Σⱼ wᵢ wⱼ |rᵢ − rⱼ| / (2 (Σwᵢ)² r̄)

    wᵢ = demand_tons[i]  (volume weight)
    rᵢ = fulfillment ratio for node i, capped at 1.0

    Returns 0.0 when all fulfillment ratios are identical (uniform allocation).
    Returns near-maximum when one node gets everything and others get nothing.

    Verification:
        gini({k: 1 for all k}, equal weights) == 0.0
        gini({k: 0 for all k except one}, equal weights) > 0.6
        uniform allocation produces Gini ≈ 0 (all ratios equal)
    """
    nodes = [(k, v) for k, v in demand_tons.items() if v > 0]
    if not nodes:
        return 0.0

    ratios = [min(1.0, matched_tons.get(k, 0.0) / v) for k, v in nodes]
    weights = [v for _, v in nodes]

    w_sum = sum(weights)
    if w_sum == 0:
        return 0.0

    # Weighted mean fulfillment
    r_bar = sum(w * r for w, r in zip(weights, ratios)) / w_sum
    if r_bar == 0:
        return 0.0

    # Double-sum formulation: O(n²) but n is at most ~38*19*4 ≈ 2888 for Jatim.
    # Formula: G = Σ_all_ij wᵢwⱼ|rᵢ−rⱼ| / (2 w_sum² r̄)
    # Σ_all_ij = 2 * Σ_{i<j}  (since |rᵢ−rⱼ| is symmetric and diagonal is 0).
    # Therefore: G = 2*Σ_{i<j} wᵢwⱼ|rᵢ−rⱼ| / (2 w_sum² r̄) = Σ_{i<j} / (w_sum² r̄).
    total = 0.0
    n = len(ratios)
    for i in range(n):
        for j in range(i + 1, n):
            total += weights[i] * weights[j] * abs(ratios[i] - ratios[j])
    return total / (w_sum ** 2 * r_bar)


def atkinson(
    matched_tons: Dict[_Key, float],
    demand_tons: Dict[_Key, float],
    epsilon: float = 0.5,
) -> float:
    """
    Atkinson inequality index A(ε).

    For ε ≠ 1:
        A(ε) = 1 − (1/μ) * (Σᵢ wᵢ rᵢ^(1−ε) / Σᵢ wᵢ)^(1/(1−ε))

    For ε = 1 (limiting case):
        A(1) = 1 − exp(Σᵢ wᵢ ln(rᵢ) / Σᵢ wᵢ) / μ

    wᵢ = demand_tons weight.
    rᵢ = fulfillment ratio capped at 1.0.
    rᵢ = 0 clamped to 1e-9 before log (standard handling).

    Returns value in [0.0, 1.0]; higher means more inequality.
    """
    nodes = [(k, v) for k, v in demand_tons.items() if v > 0]
    if not nodes:
        return 0.0

    ratios = [min(1.0, matched_tons.get(k, 0.0) / v) for k, v in nodes]
    weights = [v for _, v in nodes]

    w_sum = sum(weights)
    if w_sum == 0:
        return 0.0

    mu = sum(w * r for w, r in zip(weights, ratios)) / w_sum
    if mu == 0:
        return 1.0  # everyone gets nothing → maximum inequality by convention

    if abs(epsilon - 1.0) < 1e-9:
        # Geometric mean formulation
        log_sum = sum(
            w * math.log(max(r, 1e-9)) for w, r in zip(weights, ratios)
        )
        geom_mean = math.exp(log_sum / w_sum)
        return 1.0 - geom_mean / mu
    else:
        power = 1.0 - epsilon
        moment = sum(
            w * (max(r, 1e-9) ** power) for w, r in zip(weights, ratios)
        ) / w_sum
        ede = moment ** (1.0 / power)
        return 1.0 - ede / mu


def min_fulfillment(
    matched_tons: Dict[_Key, float],
    demand_tons: Dict[_Key, float],
) -> float:
    """
    Leximin gap: fulfillment ratio of the single worst-served demand node.

    A strategy that sacrifices one kab entirely will score 0.0 here.
    Higher is better.

    Returns 0.0 if there are no demand nodes.
    """
    nodes = [(k, v) for k, v in demand_tons.items() if v > 0]
    if not nodes:
        return 0.0
    ratios = [min(1.0, matched_tons.get(k, 0.0) / v) for k, v in nodes]
    return min(ratios)


def kab_fulfillment(
    matched_tons: Dict[_Key, float],
    demand_tons: Dict[_Key, float],
    kab_id: str,
) -> float:
    """
    Volume-weighted fulfillment ratio for a single kabupaten across all
    its (commodity, segment) demand nodes.

    Used for Sampang (3527) and Bangkalan (3526) headline pitch numbers.

    Returns 0.0 if kab_id has no demand entries.
    """
    kab_demand = {k: v for k, v in demand_tons.items() if k[0] == kab_id}
    if not kab_demand:
        return 0.0
    total_demand = sum(kab_demand.values())
    if total_demand == 0:
        return 0.0
    total_matched = sum(
        min(matched_tons.get(k, 0.0), v) for k, v in kab_demand.items()
    )
    return total_matched / total_demand
