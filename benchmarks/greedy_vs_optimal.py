"""
benchmarks/greedy_vs_optimal.py — Greedy vs exact optimal, on AgriFlow's own
score/cost structure.

WHY THIS SCRIPT EXISTS
-----------------------
HANDOFF.md (2026-05-19) HOLDs the POT/EMD (optimal transport) allocator on the
claim: "AgriFlow pakai single shared score function -> solusi POT/EMD pada cost
matrix saat ini identik atau hampir-identik dengan greedy." That claim rests on
ONE 3x3 toy example where greedy happened to match brute-force optimal (2.720).

A single-instance coincidence is not evidence. This script settles the question
empirically and reproducibly, in two parts:

  PART A — Assignment case (1-to-1 matching, no volume splitting):
      A1. Pure uniform-random scores (baseline literature check).
      A2. AgriFlow-structured scores: built from the project's own
          ScoreBreakdown.weighted_total() (22/22/22/18/16 weights,
          matching_engine/models.py), with correlated supply/demand
          "quality" so the instances are not adversarial.
      Compared: naive greedy (repeatedly take the best remaining pair) vs
      scipy.optimize.linear_sum_assignment (Hungarian algorithm, EXACT optimal).
      For n<=6 the Hungarian result is cross-checked against brute-force
      permutation search as a correctness sanity check on the solver itself.

  PART B — Capacitated / divisible case (the actual production shape):
      Runs the REAL engine pipeline — matching_engine.constraints.generate_candidates
      (Layer 1 hard constraints) + matching_engine.scoring.compute_score (Layer 2,
      DEFAULT_WEIGHTS) + matching_engine.allocation equity/segment multipliers —
      on (a) the project's real Jatim sample data (sample_data/surplus_deficit.csv)
      and (b) synthetic Indonesia-scale workloads (reusing benchmarks/national_scale
      generators) at increasing kab counts.
      Compared: the SHIPPED allocators (stable_match_tier1 via force_strategy=
      "stable", greedy_match_tier2 via force_strategy="greedy") vs the exact
      capacitated transportation optimum, solved as an LP with scipy.optimize.linprog
      (HiGHS): maximize sum(final_score_e * x_e) subject to per-supply-node and
      per-deficit-node capacity constraints, 0 <= x_e <= min(supply, demand).
      This LP is the textbook optimal solution to the "correct" framing raised
      separately (capacitated min-cost transportation, not 1-1 assignment) — it
      is what network-simplex / ot.emd-with-partial-mass would also converge to.

      Also reports STRANDED VOLUME for the 1-1 stable matcher: how much supply/
      demand tonnage is left on the table because stable_match_tier1 matches at
      most one deficit per surplus node (min(s,d) then abandon), vs the LP/greedy
      which can split a big surplus across many small deficits.

Everything is seeded (--seed, default 2026) for reproducibility. No network
calls, no writes outside benchmarks/output/.

Usage:
    python benchmarks/greedy_vs_optimal.py
    python benchmarks/greedy_vs_optimal.py --skip-real     # synthetic sweeps only (fast)
    python benchmarks/greedy_vs_optimal.py --seed 7
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import random
import statistics
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Callable, List, Optional, Sequence, Tuple

import numpy as np
from scipy.optimize import linear_sum_assignment, linprog

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from matching_engine.allocation import (
    allocate, equity_multiplier_value, segment_multiplier_value,
)
from matching_engine.constraints import generate_candidates
from matching_engine.models import LogisticsContext, ScoreBreakdown
from matching_engine.scoring import DEFAULT_WEIGHTS, compute_score
from sample_data.loader import load_all_sample_data

DEFAULT_SEED = 2026


# =============================================================================
# PART A — ASSIGNMENT CASE (1-to-1, no volume splitting)
# =============================================================================

def brute_force_optimal(score: np.ndarray) -> float:
    """Exact optimal via exhaustive permutation search. Only for n <= 8."""
    n, m = score.shape
    assert n == m, "brute force sanity check only used on square matrices here"
    best = -1.0
    for perm in itertools.permutations(range(n)):
        total = sum(score[i, perm[i]] for i in range(n))
        if total > best:
            best = total
    return best


def hungarian_optimal(score: np.ndarray) -> Tuple[float, List[Tuple[int, int]]]:
    """Exact optimal assignment (max total score) via scipy Hungarian algorithm."""
    row_ind, col_ind = linear_sum_assignment(-score)  # minimize negative = maximize
    total = float(score[row_ind, col_ind].sum())
    pairs = list(zip(row_ind.tolist(), col_ind.tolist()))
    return total, pairs


def greedy_assignment(score: np.ndarray) -> Tuple[float, List[Tuple[int, int]]]:
    """
    Naive greedy 1-1 assignment: repeatedly take the globally best remaining
    (row, col) pair. This is the abstraction of what stable_match_tier1 /
    greedy_match_tier2 do at the single-score level (both eventually assign the
    best-scoring available counterpart first).
    """
    n, m = score.shape
    flat = [(score[i, j], i, j) for i in range(n) for j in range(m)]
    flat.sort(key=lambda t: -t[0])
    used_rows, used_cols = set(), set()
    pairs = []
    total = 0.0
    for s, i, j in flat:
        if i in used_rows or j in used_cols:
            continue
        used_rows.add(i)
        used_cols.add(j)
        pairs.append((i, j))
        total += s
        if len(used_rows) == min(n, m):
            break
    return total, pairs


@dataclass
class AssignmentTrialResult:
    n: int
    trial: int
    greedy_total: float
    optimal_total: float
    gap_pct: float           # (optimal - greedy) / optimal * 100
    greedy_lost: bool        # strictly worse than optimal


def run_assignment_sweep(
    label: str,
    ns: Sequence[int],
    trials: int,
    make_score_matrix: Callable[[int, random.Random], np.ndarray],
    seed: int,
    sanity_check_bruteforce: bool = True,
) -> List[AssignmentTrialResult]:
    results: List[AssignmentTrialResult] = []
    rng = random.Random(seed)

    print(f"\n{'=' * 78}")
    print(f"  PART A — {label}")
    print(f"{'=' * 78}")

    for n in ns:
        losses = 0
        gaps = []
        for t in range(trials):
            score = make_score_matrix(n, rng)
            greedy_total, _ = greedy_assignment(score)
            optimal_total, _ = hungarian_optimal(score)

            if sanity_check_bruteforce and n <= 6 and t == 0:
                bf = brute_force_optimal(score)
                assert abs(bf - optimal_total) < 1e-6, (
                    f"Hungarian ({optimal_total}) != brute force ({bf}) at n={n} — "
                    f"solver correctness check failed"
                )

            gap_pct = (
                0.0 if optimal_total <= 1e-12
                else (optimal_total - greedy_total) / optimal_total * 100.0
            )
            lost = greedy_total < optimal_total - 1e-9
            if lost:
                losses += 1
            gaps.append(gap_pct)
            results.append(AssignmentTrialResult(
                n=n, trial=t, greedy_total=greedy_total,
                optimal_total=optimal_total, gap_pct=gap_pct, greedy_lost=lost,
            ))

        mean_gap = statistics.mean(gaps)
        median_gap = statistics.median(gaps)
        worst_gap = max(gaps)
        print(f"  n={n:>3}  trials={trials:>4}  greedy lost {losses:>4}/{trials} "
              f"({losses / trials * 100:5.1f}%)  mean_gap={mean_gap:6.2f}%  "
              f"median_gap={median_gap:6.2f}%  worst_gap={worst_gap:6.2f}%")

    return results


def make_uniform_score_matrix(n: int, rng: random.Random) -> np.ndarray:
    """Pure iid uniform random scores in [0, 1] — n x n."""
    return np.array([[rng.random() for _ in range(n)] for _ in range(n)])


def make_agriflow_structured_score_matrix(n: int, rng: random.Random) -> np.ndarray:
    """
    n x n score matrix built from the project's OWN ScoreBreakdown.weighted_total()
    (22/22/22/18/16 weights, matching_engine/models.py) instead of an abstract
    number. Supply node i has a fixed "quality" vector; deficit node j has a fixed
    "preference" vector; per-pair dimension score = clip(quality_i + pref_j + noise,
    0, 1). This gives correlated, non-adversarial instances structurally similar to
    a real (supply, deficit) grid, while still being driven by the actual weighted-
    sum formula the engine uses everywhere.
    """
    dims = 5  # distance, volume, price, perishability, climate
    supply_quality = [[rng.random() for _ in range(dims)] for _ in range(n)]
    demand_pref = [[rng.random() for _ in range(dims)] for _ in range(n)]

    score = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            vals = []
            for d in range(dims):
                noise = rng.gauss(0, 0.10)
                v = 0.5 * supply_quality[i][d] + 0.5 * demand_pref[j][d] + noise
                vals.append(min(1.0, max(0.0, v)))
            breakdown = ScoreBreakdown(
                distance=vals[0], volume=vals[1], price=vals[2],
                perishability=vals[3], climate=vals[4],
            )
            score[i, j] = breakdown.weighted_total()  # 0-100 scale, project's own formula
    return score


# =============================================================================
# PART B — CAPACITATED / DIVISIBLE CASE (real engine pipeline)
# =============================================================================

@dataclass
class CapacitatedResult:
    label: str
    n_supply: int
    n_deficit: int
    n_candidates: int
    total_supply_tons: float
    total_deficit_tons: float
    stable_welfare: float
    stable_matched_tons: float
    stable_n_matches: int
    greedy_welfare: float
    greedy_matched_tons: float
    greedy_n_matches: int
    lp_optimal_welfare: float
    lp_optimal_matched_tons: float
    lp_status: str
    stable_gap_pct: float     # vs LP optimal welfare
    greedy_gap_pct: float     # vs LP optimal welfare
    stable_stranded_tons: float   # total_supply_tons - stable_matched_tons
    lp_stranded_tons: float       # total_supply_tons - lp_optimal_matched_tons


def _final_score(s, d, base_score: float) -> float:
    eq_mult = equity_multiplier_value(d.kabupaten.ipm)
    seg_mult, _flags = segment_multiplier_value(s, d)
    return base_score * eq_mult * seg_mult


def solve_capacitated_transportation_lp(
    candidates: List[Tuple], score_fn: Callable,
) -> Tuple[float, float, str, dict]:
    """
    Exact optimal for the capacitated (divisible) transportation problem on the
    SAME candidate pool the engine itself uses (post Layer-1 filtering).

    max  sum_e final_score_e * x_e
    s.t. for each supply node i: sum_{e incident to i} x_e <= supply_volume_i
         for each deficit node j: sum_{e incident to j} x_e <= deficit_volume_j
         0 <= x_e <= min(supply_i, deficit_j)   (per-edge bound, redundant but tightens LP)

    Solved with scipy.optimize.linprog (HiGHS). Returns (optimal_welfare,
    optimal_matched_tons, lp_status, edge_solution) where edge_solution maps
    edge index -> tons matched.
    """
    if not candidates:
        return 0.0, 0.0, "no_candidates", {}

    supply_keys, deficit_keys = {}, {}
    edges = []  # (supply_idx, deficit_idx, final_score, cap, s, d)
    score_cache = {}

    for s, d in candidates:
        s_key = s.kabupaten.id + "_" + s.commodity.code
        d_key = d.kabupaten.id + "_" + d.commodity.code + "_" + d.segment.value
        if s_key not in supply_keys:
            supply_keys[s_key] = (len(supply_keys), s.volume_tons)
        if d_key not in deficit_keys:
            deficit_keys[d_key] = (len(deficit_keys), d.volume_tons)

        cache_key = (s_key, d.kabupaten.id + "_" + d.commodity.code)
        if cache_key not in score_cache:
            _breakdown, base_score, _dist = score_fn(s, d)
            score_cache[cache_key] = _final_score(s, d, base_score)
        fscore = score_cache[cache_key]

        s_idx = supply_keys[s_key][0]
        d_idx = deficit_keys[d_key][0]
        cap = min(s.volume_tons, d.volume_tons)
        edges.append((s_idx, d_idx, fscore, cap))

    n_edges = len(edges)
    n_supply = len(supply_keys)
    n_deficit = len(deficit_keys)

    c = np.array([-e[2] for e in edges])  # minimize negative = maximize welfare
    bounds = [(0.0, e[3]) for e in edges]

    A_ub = np.zeros((n_supply + n_deficit, n_edges))
    b_ub = np.zeros(n_supply + n_deficit)
    for s_key, (idx, vol) in supply_keys.items():
        b_ub[idx] = vol
    for d_key, (idx, vol) in deficit_keys.items():
        b_ub[n_supply + idx] = vol
    for e_idx, (s_idx, d_idx, _fscore, _cap) in enumerate(edges):
        A_ub[s_idx, e_idx] = 1.0
        A_ub[n_supply + d_idx, e_idx] = 1.0

    res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")

    if not res.success:
        return 0.0, 0.0, f"lp_failed:{res.message}", {}

    optimal_welfare = float(-res.fun)
    matched_tons = float(res.x.sum())
    edge_solution = {i: float(x) for i, x in enumerate(res.x) if x > 1e-9}
    return optimal_welfare, matched_tons, "optimal", edge_solution


def evaluate_capacitated(
    label: str, surplus, deficit, logistics: Optional[LogisticsContext] = None,
) -> CapacitatedResult:
    logistics = logistics or LogisticsContext()
    candidates = generate_candidates(surplus, deficit, logistics=logistics)

    def score_fn(s, d):
        return compute_score(s, d, logistics=logistics, weights=DEFAULT_WEIGHTS)

    total_supply_tons = sum(s.volume_tons for s in surplus)
    total_deficit_tons = sum(d.volume_tons for d in deficit)

    if not candidates:
        return CapacitatedResult(
            label=label, n_supply=len(surplus), n_deficit=len(deficit),
            n_candidates=0, total_supply_tons=total_supply_tons,
            total_deficit_tons=total_deficit_tons,
            stable_welfare=0.0, stable_matched_tons=0.0, stable_n_matches=0,
            greedy_welfare=0.0, greedy_matched_tons=0.0, greedy_n_matches=0,
            lp_optimal_welfare=0.0, lp_optimal_matched_tons=0.0, lp_status="no_candidates",
            stable_gap_pct=0.0, greedy_gap_pct=0.0,
            stable_stranded_tons=total_supply_tons, lp_stranded_tons=total_supply_tons,
        )

    matches_stable = allocate(candidates, score_fn, force_strategy="stable",
                               equity_fn=equity_multiplier_value)
    matches_greedy = allocate(candidates, score_fn, force_strategy="greedy",
                               equity_fn=equity_multiplier_value)

    stable_welfare = sum(m.final_score * m.matched_volume_tons for m in matches_stable)
    stable_matched_tons = sum(m.matched_volume_tons for m in matches_stable)
    greedy_welfare = sum(m.final_score * m.matched_volume_tons for m in matches_greedy)
    greedy_matched_tons = sum(m.matched_volume_tons for m in matches_greedy)

    lp_welfare, lp_matched_tons, lp_status, _sol = solve_capacitated_transportation_lp(
        candidates, score_fn,
    )

    def gap(engine_welfare: float) -> float:
        if lp_welfare <= 1e-9:
            return 0.0
        return (lp_welfare - engine_welfare) / lp_welfare * 100.0

    return CapacitatedResult(
        label=label, n_supply=len(surplus), n_deficit=len(deficit),
        n_candidates=len(candidates),
        total_supply_tons=total_supply_tons, total_deficit_tons=total_deficit_tons,
        stable_welfare=stable_welfare, stable_matched_tons=stable_matched_tons,
        stable_n_matches=len(matches_stable),
        greedy_welfare=greedy_welfare, greedy_matched_tons=greedy_matched_tons,
        greedy_n_matches=len(matches_greedy),
        lp_optimal_welfare=lp_welfare, lp_optimal_matched_tons=lp_matched_tons,
        lp_status=lp_status,
        stable_gap_pct=gap(stable_welfare), greedy_gap_pct=gap(greedy_welfare),
        stable_stranded_tons=total_supply_tons - stable_matched_tons,
        lp_stranded_tons=total_supply_tons - lp_matched_tons,
    )


def print_capacitated_result(r: CapacitatedResult) -> None:
    print(f"\n  --- {r.label} ---")
    print(f"  supply={r.n_supply}  deficit={r.n_deficit}  candidates={r.n_candidates}  "
          f"total_supply={r.total_supply_tons:,.0f}t  total_deficit={r.total_deficit_tons:,.0f}t")
    print(f"  {'strategy':<22}{'welfare':>14}{'matched_tons':>16}{'n_matches':>12}{'gap_vs_LP':>12}")
    print(f"  {'stable (shipped)':<22}{r.stable_welfare:>14,.1f}{r.stable_matched_tons:>16,.1f}"
          f"{r.stable_n_matches:>12}{r.stable_gap_pct:>11.2f}%")
    print(f"  {'greedy (shipped)':<22}{r.greedy_welfare:>14,.1f}{r.greedy_matched_tons:>16,.1f}"
          f"{r.greedy_n_matches:>12}{r.greedy_gap_pct:>11.2f}%")
    print(f"  {'LP optimal (exact)':<22}{r.lp_optimal_welfare:>14,.1f}{r.lp_optimal_matched_tons:>16,.1f}"
          f"{'-':>12}{'0.00%':>12}   [{r.lp_status}]")
    print(f"  stranded supply tons: stable={r.stable_stranded_tons:,.1f}t  "
          f"LP-optimal={r.lp_stranded_tons:,.1f}t  "
          f"(extra tonnage LP moves that stable abandons: "
          f"{r.stable_stranded_tons - r.lp_stranded_tons:,.1f}t)")


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Greedy vs exact-optimal benchmark for AgriFlow's allocator "
                     "(settles HANDOFF.md's POT/EMD HOLD premise with evidence).",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--trials", type=int, default=200,
                         help="Trials per n in the assignment sweeps (default 200)")
    parser.add_argument("--skip-real", action="store_true",
                         help="Skip Part B real-data / synthetic-Indonesia runs (faster)")
    parser.add_argument("--json-out", type=str, default=None,
                         help="Optional path to write full results as JSON")
    args = parser.parse_args()

    t0 = time.perf_counter()
    print("=" * 78)
    print(f"  AgriFlow — Greedy vs Exact Optimal  (seed={args.seed}, "
          f"trials/n={args.trials})")
    print(f"  Run: {datetime.now().isoformat(timespec='seconds')}")
    print("=" * 78)

    all_results: dict = {"seed": args.seed, "trials": args.trials}

    ns = [3, 4, 5, 6, 7, 10, 12, 15, 20]

    a1 = run_assignment_sweep(
        "A1 — Pure uniform-random scores (assignment case)",
        ns, args.trials, make_uniform_score_matrix, args.seed,
    )
    a2 = run_assignment_sweep(
        "A2 — AgriFlow-structured scores (ScoreBreakdown.weighted_total, "
        "correlated supply/demand)",
        ns, args.trials, make_agriflow_structured_score_matrix, args.seed + 1,
    )
    all_results["part_a_uniform"] = [asdict(r) for r in a1]
    all_results["part_a_agriflow_structured"] = [asdict(r) for r in a2]

    if not args.skip_real:
        print(f"\n{'=' * 78}")
        print("  PART B — Capacitated transportation (real engine pipeline)")
        print(f"{'=' * 78}")

        cap_results: List[CapacitatedResult] = []

        # B1 — Real Jatim sample data (the project's actual demo dataset)
        data = load_all_sample_data()
        r_real = evaluate_capacitated(
            "B1 — Real Jatim sample data (sample_data/surplus_deficit.csv, 38 kab)",
            data["surplus"], data["deficit"],
        )
        print_capacitated_result(r_real)
        cap_results.append(r_real)

        # B2 — Synthetic Indonesia-scale workloads at increasing kab counts,
        # reusing the project's own national_scale.py generators (real Commodity
        # specs, realistic IPM/tier distribution).
        sys.path.insert(0, os.path.join(ROOT, "benchmarks"))
        import national_scale as ns_bench  # project's own synthetic generator

        rng_synth = random.Random(args.seed)
        random.seed(args.seed)  # national_scale generators use the global random module
        for n_kab in (38, 100, 250):
            kabs = ns_bench.make_synthetic_indonesia(n_kab)
            surplus, deficit = ns_bench.make_workload(kabs, n_commodities=19)
            r = evaluate_capacitated(
                f"B2 — Synthetic Indonesia-scale ({n_kab} kab x 19 komoditas)",
                surplus, deficit,
            )
            print_capacitated_result(r)
            cap_results.append(r)

        all_results["part_b_capacitated"] = [asdict(r) for r in cap_results]

    elapsed = time.perf_counter() - t0
    print(f"\n{'=' * 78}")
    print(f"  Done in {elapsed:.1f}s")
    print("=" * 78)

    if args.json_out:
        def _json_default(o):
            if isinstance(o, (np.floating, np.integer)):
                return o.item()
            if isinstance(o, np.bool_):
                return bool(o)
            raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")

        os.makedirs(os.path.dirname(args.json_out) or ".", exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(all_results, fh, indent=2, default=_json_default)
        print(f"  Full results written to {args.json_out}")


if __name__ == "__main__":
    main()
