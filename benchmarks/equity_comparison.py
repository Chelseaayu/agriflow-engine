"""
benchmarks/equity_comparison.py — Baseline Comparison + Equity Sensitivity Harness.

Action 2 (baseline comparison) + Action 6 (sensitivity) from recommendation.md.
Generates two pitch tables and writes them to benchmarks/output/equity_comparison.md.

Five strategies:
    1. pure_greedy       — equity_fn=lambda _: 1.0, force_strategy="greedy"
                           Efficiency anchor (honest frontier: no equity).
    2. agriflow          — default equity_fn + default dispatch
                           Production behavior.
    3. uniform           — equal split per surplus across viable deficits
                           Equity anchor (ignores score entirely).
    4. proportional      — allocation proportional to deficit magnitude per kab
                           Status-quo Bapanas foil (attack #7 answer).
    5. agriflow_smoothed — linear-interpolation closure over existing tier knots
                           (1.30/1.15/1.05/1.00 at IPM 68/72/78), no new params.
                           Demonstrates smoothed ≈ step (attack #2 answer).

All five strategies receive IDENTICAL inputs: same supply/deficit pool, same
logistics context, same hard constraints (generate_candidates). Only
scoring/prioritisation differs. This is the apple-to-apple requirement.

Run:
    python benchmarks/equity_comparison.py
"""
from __future__ import annotations
import os
import sys
from collections import defaultdict
from typing import Dict, List, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from matching_engine import run_matching
from matching_engine.allocation import equity_multiplier_value
from matching_engine.constraints import generate_candidates
from matching_engine.models import LogisticsContext
from sample_data.loader import load_all_sample_data

from benchmarks._metrics import (
    atkinson,
    fulfillment_by_node,
    gini,
    kab_fulfillment,
    min_fulfillment,
    total_deficit_covered,
)

# ---------------------------------------------------------------------------
# Key type: (kab_id, commodity_code, segment_value) -> float
# ---------------------------------------------------------------------------
_Key = Tuple[str, str, str]

SAMPANG_ID = "3527"
BANGKALAN_ID = "3526"


# ---------------------------------------------------------------------------
# HELPER: extract demand_tons dict from loaded deficit nodes
# ---------------------------------------------------------------------------

def _build_demand_tons(deficit_nodes) -> Dict[_Key, float]:
    """Build demand_tons dict from a list of DemandNode objects."""
    out: Dict[_Key, float] = {}
    for d in deficit_nodes:
        key = (d.kabupaten.id, d.commodity.code, d.segment.value)
        out[key] = out.get(key, 0.0) + d.volume_tons
    return out


# ---------------------------------------------------------------------------
# HELPER: extract matched_tons dict from a MatchingReport
# ---------------------------------------------------------------------------

def _report_to_matched_tons(report) -> Dict[_Key, float]:
    """Adapt MatchingReport.matches -> matched_tons dict."""
    out: Dict[_Key, float] = {}
    for m in report.matches:
        key = (m.deficit.kabupaten.id, m.deficit.commodity.code, m.deficit.segment.value)
        out[key] = out.get(key, 0.0) + m.matched_volume_tons
    return out


# ---------------------------------------------------------------------------
# STRATEGY 3: UNIFORM ALLOCATION
# Uses only Layer 1 candidate generation; ignores score entirely.
# Each surplus splits its volume equally across its viable deficits,
# capping at each deficit's actual need.
# ---------------------------------------------------------------------------

def uniform_allocate(surplus, deficit, logistics) -> Dict[_Key, float]:
    """
    Equity baseline: each surplus splits volume equally across its viable
    deficit partners (post hard-constraint). Score is ignored entirely.

    Returns matched_tons dict: (kab_id, commodity_code, segment) -> tons matched.
    This is a foil only — not a product feature, implemented in benchmarks/.
    """
    candidates = generate_candidates(surplus, deficit, logistics=logistics)

    # Group: surplus_key -> list of deficit nodes that can receive it
    surplus_to_deficits: Dict[str, List] = defaultdict(list)
    for s, d in candidates:
        s_key = s.kabupaten.id + "_" + s.commodity.code
        surplus_to_deficits[s_key].append((s, d))

    # Build demand lookup: (kab_id, commodity, segment) -> total_demand
    demand_lookup: Dict[_Key, float] = _build_demand_tons(deficit)

    # remaining demand per key
    remaining_demand: Dict[_Key, float] = dict(demand_lookup)
    matched: Dict[_Key, float] = defaultdict(float)

    # For each surplus, distribute its volume equally across eligible deficits
    # Iterate multiple passes to handle partial fills (demand may already be
    # partially filled from another surplus). Simple single-pass equal split:
    # divide surplus volume by number of eligible deficit keys.
    for s_key, pairs in surplus_to_deficits.items():
        s = pairs[0][0]
        remaining_supply = s.volume_tons
        eligible = [
            (s_, d) for s_, d in pairs
            if remaining_demand.get(
                (d.kabupaten.id, d.commodity.code, d.segment.value), 0.0
            ) > 0
        ]
        if not eligible:
            continue
        n = len(eligible)
        share = remaining_supply / n  # equal share per eligible deficit
        for _, d in eligible:
            d_key = (d.kabupaten.id, d.commodity.code, d.segment.value)
            allocation = min(share, remaining_demand.get(d_key, 0.0))
            matched[d_key] += allocation
            remaining_demand[d_key] = max(0.0, remaining_demand[d_key] - allocation)

    return dict(matched)


# ---------------------------------------------------------------------------
# STRATEGY 4: PROPORTIONAL-TO-DEFICIT (Bapanas status-quo foil)
# Allocates each surplus proportionally to the deficit magnitude of each
# eligible kab. Larger deficit gets larger share.
# ---------------------------------------------------------------------------

def proportional_allocate(surplus, deficit, logistics) -> Dict[_Key, float]:
    """
    Status-quo Bapanas foil: allocation proportional to deficit magnitude.

    Each surplus distributes volume to eligible deficits weighted by
    their remaining demand volume. Ignores score, distance ranking, equity.
    Represents a simple pro-rata rule: 'give more to those who need more'.

    Returns matched_tons dict: (kab_id, commodity_code, segment) -> tons.
    """
    candidates = generate_candidates(surplus, deficit, logistics=logistics)

    surplus_to_deficits: Dict[str, List] = defaultdict(list)
    for s, d in candidates:
        s_key = s.kabupaten.id + "_" + s.commodity.code
        surplus_to_deficits[s_key].append((s, d))

    demand_lookup: Dict[_Key, float] = _build_demand_tons(deficit)
    remaining_demand: Dict[_Key, float] = dict(demand_lookup)
    matched: Dict[_Key, float] = defaultdict(float)

    for s_key, pairs in surplus_to_deficits.items():
        s = pairs[0][0]
        remaining_supply = s.volume_tons
        eligible = [
            (s_, d) for s_, d in pairs
            if remaining_demand.get(
                (d.kabupaten.id, d.commodity.code, d.segment.value), 0.0
            ) > 0
        ]
        if not eligible:
            continue
        # Weight = remaining demand magnitude
        d_keys = [
            (d.kabupaten.id, d.commodity.code, d.segment.value)
            for _, d in eligible
        ]
        weights = [remaining_demand[k] for k in d_keys]
        total_weight = sum(weights)
        if total_weight == 0:
            continue
        for d_key, w in zip(d_keys, weights):
            share = remaining_supply * (w / total_weight)
            allocation = min(share, remaining_demand[d_key])
            matched[d_key] += allocation
            remaining_demand[d_key] = max(0.0, remaining_demand[d_key] - allocation)

    return dict(matched)


# ---------------------------------------------------------------------------
# STRATEGY 5: AGRIFLOW-SMOOTHED (linear interpolation over existing knots)
# This is a closure ONLY — do not modify equity_multiplier_value production.
# Knots: (68, 1.30), (72, 1.15), (78, 1.05), (inf, 1.00)
# Linear interpolation between knots; outside range uses boundary values.
# ---------------------------------------------------------------------------

def _equity_smoothed(ipm: float) -> float:
    """
    Linear interpolation over the existing tier knots.
    Knot values match equity_multiplier_value exactly at knot boundaries:
        IPM=68 -> 1.30, IPM=72 -> 1.15, IPM=78 -> 1.05, IPM>=85 -> 1.00

    Below 68: returns 1.30 (same as step-function).
    Between knots: linear interpolation.
    Above 85: returns 1.00.

    This demonstrates that smoothed behaviour approximates the step-function
    (attack #2 answer) without changing any production code.
    """
    # Knot points: (ipm, multiplier)
    knots = [(68.0, 1.30), (72.0, 1.15), (78.0, 1.05), (85.0, 1.00)]
    if ipm <= knots[0][0]:
        return knots[0][1]
    if ipm >= knots[-1][0]:
        return knots[-1][1]
    for i in range(len(knots) - 1):
        x0, y0 = knots[i]
        x1, y1 = knots[i + 1]
        if x0 <= ipm <= x1:
            t = (ipm - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return 1.00  # unreachable


# ---------------------------------------------------------------------------
# ACTION 6 — SENSITIVITY: three threshold variants
# ---------------------------------------------------------------------------

def equity_strict(ipm: float) -> float:
    """Strict thresholds: 1.50/1.25/1.10/1.00 at IPM <65/<70/<75/>=75."""
    if ipm < 65:
        return 1.50
    elif ipm < 70:
        return 1.25
    elif ipm < 75:
        return 1.10
    else:
        return 1.00


def equity_current(ipm: float) -> float:
    """Current (production) thresholds — delegates to equity_multiplier_value.
    Single source of truth: this column in the sensitivity table IS the
    shipped behavior, not a re-typed copy that could drift."""
    return equity_multiplier_value(ipm)


def equity_lenient(ipm: float) -> float:
    """Lenient thresholds: 1.15/1.08/1.03/1.00 at IPM <70/<75/<80/>=80."""
    if ipm < 70:
        return 1.15
    elif ipm < 75:
        return 1.08
    elif ipm < 80:
        return 1.03
    else:
        return 1.00


# ---------------------------------------------------------------------------
# BOUNDARY PERTURBATION — how many Jatim kabs change tier under ±1/±2 shifts
# ---------------------------------------------------------------------------

def boundary_perturbation(kabupaten_dict: dict) -> dict:
    """
    Shift each IPM threshold by ±1 and ±2 points and count how many
    Jatim kabupaten change tier (i.e. receive a different multiplier).

    Thresholds being perturbed: 68, 72, 78 (the three break points in
    equity_multiplier_value for Jatim 2024).

    Returns a dict with counts per shift magnitude for each threshold.
    """
    ipm_values = [k.ipm for k in kabupaten_dict.values()]

    def count_different(delta: float) -> int:
        """Count kabs whose multiplier changes when ALL thresholds shift by delta."""
        changed = 0
        for ipm in ipm_values:
            orig = equity_multiplier_value(ipm)
            # Shifted function: thresholds 68->68+delta, 72->72+delta, 78->78+delta
            t68 = 68.0 + delta
            t72 = 72.0 + delta
            t78 = 78.0 + delta
            if ipm < t68:
                shifted = 1.30
            elif ipm < t72:
                shifted = 1.15
            elif ipm < t78:
                shifted = 1.05
            else:
                shifted = 1.00
            if abs(orig - shifted) > 1e-9:
                changed += 1
        return changed

    result = {}
    for delta in (-2.0, -1.0, +1.0, +2.0):
        result[delta] = count_different(delta)
    return result


# ---------------------------------------------------------------------------
# COMPUTE METRICS ROW for a strategy
# ---------------------------------------------------------------------------

def compute_row(
    strategy_name: str,
    matched_tons: Dict[_Key, float],
    demand_tons: Dict[_Key, float],
) -> dict:
    """Compute all 5 metric columns for one strategy."""
    return {
        "strategy": strategy_name,
        "total_deficit_covered": total_deficit_covered(matched_tons, demand_tons),
        "gini": gini(matched_tons, demand_tons),
        "atkinson_05": atkinson(matched_tons, demand_tons, epsilon=0.5),
        "atkinson_10": atkinson(matched_tons, demand_tons, epsilon=1.0),
        "min_fulfillment": min_fulfillment(matched_tons, demand_tons),
        "sampang": kab_fulfillment(matched_tons, demand_tons, SAMPANG_ID),
        "bangkalan": kab_fulfillment(matched_tons, demand_tons, BANGKALAN_ID),
    }


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    print("=" * 80)
    print("  AGRIFLOW EQUITY COMPARISON HARNESS")
    print("=" * 80)
    print("  Loading Jatim sample data ...")

    data = load_all_sample_data()
    surplus = data["surplus"]
    deficit = data["deficit"]
    weather = data["weather"]
    # Deliberately None — see the note in equity_comparison_constrained.py. The
    # synthetic fixture's prices predate the real PIHPS stats now sitting in
    # historical_price_stats.csv, so the 3-sigma filter would drop fixture nodes and
    # confound a comparison that is about the allocation mechanism.
    historical = None
    kabupaten_dict = data["kabupaten"]
    logistics = LogisticsContext()

    demand_tons = _build_demand_tons(deficit)

    print(f"  Surplus nodes: {len(surplus)}")
    print(f"  Deficit nodes: {len(deficit)}")
    print(f"  Demand keys:   {len(demand_tons)}")
    print()

    # -----------------------------------------------------------------------
    # RUN FIVE STRATEGIES
    # All use same surplus/deficit/logistics — only equity_fn / prioritisation differs
    # -----------------------------------------------------------------------

    print("  Running strategies ...")

    # 1. Pure greedy — efficiency anchor
    report_greedy = run_matching(
        surplus, deficit,
        logistics=logistics,
        weather_forecasts=weather,
        historical_prices=historical,
        force_strategy="greedy",
        equity_fn=lambda _ipm: 1.0,
    )
    matched_greedy = _report_to_matched_tons(report_greedy)
    print("    [1/5] pure_greedy done")

    # 2. AgriFlow — default (production behavior, equity_fn omitted)
    report_agriflow = run_matching(
        surplus, deficit,
        logistics=logistics,
        weather_forecasts=weather,
        historical_prices=historical,
    )
    matched_agriflow = _report_to_matched_tons(report_agriflow)
    print("    [2/5] agriflow done")

    # 3. Uniform — equity anchor (ignores score, equal split)
    matched_uniform = uniform_allocate(surplus, deficit, logistics)
    print("    [3/5] uniform done")

    # 4. Proportional-to-deficit (Bapanas status-quo foil)
    matched_proportional = proportional_allocate(surplus, deficit, logistics)
    print("    [4/5] proportional done")

    # 5. AgriFlow-smoothed — linear interpolation over existing knots
    report_smoothed = run_matching(
        surplus, deficit,
        logistics=logistics,
        weather_forecasts=weather,
        historical_prices=historical,
        equity_fn=_equity_smoothed,
    )
    matched_smoothed = _report_to_matched_tons(report_smoothed)
    print("    [5/5] agriflow_smoothed done")
    print()

    # -----------------------------------------------------------------------
    # TABLE 1 — BASELINE COMPARISON (5 strategies × 5 metrics + kab spotlight)
    # -----------------------------------------------------------------------

    rows = [
        compute_row("pure_greedy",       matched_greedy,       demand_tons),
        compute_row("agriflow",          matched_agriflow,     demand_tons),
        compute_row("uniform",           matched_uniform,      demand_tons),
        compute_row("proportional",      matched_proportional, demand_tons),
        compute_row("agriflow_smoothed", matched_smoothed,     demand_tons),
    ]

    table1_header = (
        "| Strategy          | Coverage | Gini  | Atk(0.5) | Atk(1.0) | "
        "MinFulfill | Sampang | Bangkalan |"
    )
    table1_sep = (
        "|-------------------|----------|-------|----------|----------|"
        "-----------|---------|-----------|"
    )
    table1_lines = [table1_header, table1_sep]
    for r in rows:
        line = (
            f"| {r['strategy']:<17s} "
            f"| {r['total_deficit_covered']:.4f}   "
            f"| {r['gini']:.4f}"
            f"| {r['atkinson_05']:.4f}   "
            f"| {r['atkinson_10']:.4f}   "
            f"| {r['min_fulfillment']:.4f}    "
            f"| {r['sampang']:.4f} "
            f"| {r['bangkalan']:.4f}    |"
        )
        table1_lines.append(line)

    print("=" * 80)
    print("  TABLE 1 — BASELINE COMPARISON (5 strategies)")
    print("  Coverage = volume-weighted tons fulfilled / tons demanded")
    print("  Gini / Atkinson = weighted by demand volume (lower = more equitable)")
    print("  MinFulfill = fulfillment ratio of worst-served demand node (higher = better)")
    print("  Sampang=3527 (IPM 66.72), Bangkalan=3526 (IPM 67.70)")
    print("=" * 80)
    for line in table1_lines:
        print(line)
    print()

    # -----------------------------------------------------------------------
    # ACTION 6 — SENSITIVITY (strict / current / lenient threshold variants)
    # -----------------------------------------------------------------------

    print("  Running Action 6 sensitivity ...")

    sens_variants = [
        ("strict",  equity_strict,   "IPM <65→1.50, <70→1.25, <75→1.10, >=75→1.00"),
        ("current", equity_current,  "IPM <68→1.30, <72→1.15, <78→1.05, >=78→1.00 [PROD]"),
        ("lenient", equity_lenient,  "IPM <70→1.15, <75→1.08, <80→1.03, >=80→1.00"),
    ]

    sens_rows = []
    for name, fn, desc in sens_variants:
        rep = run_matching(
            surplus, deficit,
            logistics=logistics,
            weather_forecasts=weather,
            historical_prices=historical,
            equity_fn=fn,
        )
        mt = _report_to_matched_tons(rep)
        sens_rows.append({
            "variant": name,
            "desc": desc,
            "total_deficit_covered": total_deficit_covered(mt, demand_tons),
            "gini": gini(mt, demand_tons),
            "sampang": kab_fulfillment(mt, demand_tons, SAMPANG_ID),
            "bangkalan": kab_fulfillment(mt, demand_tons, BANGKALAN_ID),
        })

    table2_header = (
        "| Variant | Coverage | Gini  | Sampang | Bangkalan | Description |"
    )
    table2_sep = (
        "|---------|----------|-------|---------|-----------|-------------|"
    )
    table2_lines = [table2_header, table2_sep]
    for r in sens_rows:
        line = (
            f"| {r['variant']:<7s} "
            f"| {r['total_deficit_covered']:.4f}   "
            f"| {r['gini']:.4f}"
            f"| {r['sampang']:.4f} "
            f"| {r['bangkalan']:.4f}    "
            f"| {r['desc']} |"
        )
        table2_lines.append(line)

    print()
    print("=" * 80)
    print("  TABLE 2 — ACTION 6 SENSITIVITY (threshold variants)")
    print("  'current' delegates to equity_multiplier_value — single source of truth.")
    print("=" * 80)
    for line in table2_lines:
        print(line)
    print()

    # -----------------------------------------------------------------------
    # BOUNDARY PERTURBATION
    # -----------------------------------------------------------------------

    perturb = boundary_perturbation(kabupaten_dict)
    print("=" * 80)
    print("  BOUNDARY PERTURBATION — kabs changing tier when thresholds shift ±1/±2")
    print("  (Attack #2: 'cliff effect' — how sensitive is tier assignment to threshold?)")
    print("=" * 80)
    print("  Jatim IPM values (sorted):")
    ipm_sorted = sorted(k.ipm for k in kabupaten_dict.values())
    print("    " + "  ".join(f"{v:.2f}" for v in ipm_sorted))
    print()
    print("  | Threshold shift | Kabs changing tier |")
    print("  |-----------------|---------------------|")
    for delta in (-2.0, -1.0, +1.0, +2.0):
        label = f"{delta:+.0f} pts"
        print(f"  | {label:<15s} | {perturb[delta]:2d}                  |")
    print()
    print("  Interpretation:")
    print("  - 0-1 kabs per ±1pt shift = cliff effect negligible.")
    print("  - More kabs = higher sensitivity (attack #2 stronger).")
    print()

    # -----------------------------------------------------------------------
    # WRITE OUTPUT
    # -----------------------------------------------------------------------

    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "equity_comparison.md")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# AgriFlow Equity Comparison\n\n")
        f.write("Generated by `benchmarks/equity_comparison.py`.\n\n")
        f.write("## Table 1 — Baseline Comparison (5 strategies)\n\n")
        f.write("Coverage = volume-weighted tons fulfilled / tons demanded.  \n")
        f.write("Gini / Atkinson = weighted by demand volume; lower = more equitable.  \n")
        f.write("MinFulfill = fulfillment ratio of worst-served demand node; higher = better.  \n")
        f.write("Sampang=3527 (IPM 66.72), Bangkalan=3526 (IPM 67.70).  \n\n")
        for line in table1_lines:
            f.write(line + "\n")
        f.write("\n")
        f.write("## Table 2 — Action 6 Sensitivity (threshold variants)\n\n")
        f.write("`current` delegates to `equity_multiplier_value` — single source of truth.\n\n")
        for line in table2_lines:
            f.write(line + "\n")
        f.write("\n")
        f.write("## Boundary Perturbation\n\n")
        f.write("Shift all IPM thresholds simultaneously by ±1 or ±2 points.\n")
        f.write("Counts kabupaten in Jatim (38 total) that move to a different tier.\n\n")
        f.write("| Threshold shift | Kabs changing tier |\n")
        f.write("|-----------------|---------------------|\n")
        for delta in (-2.0, -1.0, +1.0, +2.0):
            label = f"{delta:+.0f} pts"
            f.write(f"| {label:<15s} | {perturb[delta]:2d}                  |\n")
        f.write("\n")

    print(f"  Tables written to: {output_path}")
    print()

    # -----------------------------------------------------------------------
    # QUICK SANITY CHECK — report potential ordering violations
    # -----------------------------------------------------------------------

    greedy_cov = rows[0]["total_deficit_covered"]
    agriflow_cov = rows[1]["total_deficit_covered"]
    greedy_gini = rows[0]["gini"]
    agriflow_gini = rows[1]["gini"]
    uniform_gini = rows[2]["gini"]
    sampang_agriflow = rows[1]["sampang"]
    sampang_greedy = rows[0]["sampang"]

    print("  ORDERING CHECKS (expected by pitch claims):")
    check = lambda ok, msg: print(f"  {'PASS' if ok else 'FAIL'} {msg}")
    check(greedy_cov >= agriflow_cov,
          f"greedy coverage ({greedy_cov:.4f}) >= agriflow coverage ({agriflow_cov:.4f})")
    check(agriflow_gini <= greedy_gini,
          f"agriflow gini ({agriflow_gini:.4f}) <= greedy gini ({greedy_gini:.4f})")
    check(uniform_gini <= agriflow_gini,
          f"uniform gini ({uniform_gini:.4f}) <= agriflow gini ({agriflow_gini:.4f})")
    check(sampang_agriflow >= sampang_greedy,
          f"Sampang: agriflow ({sampang_agriflow:.4f}) >= greedy ({sampang_greedy:.4f})")
    strict_sampang = sens_rows[0]["sampang"]
    lenient_sampang = sens_rows[2]["sampang"]
    check(strict_sampang >= lenient_sampang,
          f"strict Sampang ({strict_sampang:.4f}) >= lenient Sampang ({lenient_sampang:.4f})")

    smoothed_cov = rows[4]["total_deficit_covered"]
    smoothed_gini = rows[4]["gini"]
    check(abs(smoothed_cov - agriflow_cov) < 0.05,
          f"smoothed coverage ({smoothed_cov:.4f}) approx agriflow ({agriflow_cov:.4f})")
    check(abs(smoothed_gini - agriflow_gini) < 0.05,
          f"smoothed gini ({smoothed_gini:.4f}) approx agriflow gini ({agriflow_gini:.4f})")
    print()

    print("=" * 80)
    print("  DONE. Copy tables from benchmarks/output/equity_comparison.md into pitch deck.")
    print("=" * 80)


if __name__ == "__main__":
    main()
