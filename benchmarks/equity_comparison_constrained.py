"""
benchmarks/equity_comparison_constrained.py — Side-by-side ABUNDANT vs CONSTRAINED.

Skenario CONSTRAINED: La Nina banjir besar menghantam tiga sentra beras
utama Jatim bagian barat — Ngawi (3521), Madiun (3519), Bojonegoro (3522) —
secara bersamaan pada musim panen Oktober–November.

Narasi (defensible):
    Ngawi, Madiun, dan Bojonegoro adalah kabupaten di dataran rendah lembah
    Bengawan Solo dan anak sungainya. Ketiga kab ini secara historis mengalami
    banjir bersamaan selama fase La Nina intensitas tinggi (pola 2010, 2020–21,
    2022–23). Dalam skenario ini, banjir menghanguskan atau memotong akses ke
    6 surplus: beras_premium Bojonegoro (650t) + Ngawi (500t), beras_medium
    Madiun (1200t) + Ngawi (900t), jagung Bojonegoro (800t) + Ngawi (600t).
    Total supply yang hilang: 4.650 ton.

Arithmetic:
    ABUNDANT: surplus=8.612t, deficit=5.249t, ratio=1.641 (melimpah)
    CONSTRAINED: surplus=3.962t, deficit=5.249t, ratio=0.754 (kekurangan 32.5%)

Fixture:
    sample_data/surplus_deficit_constrained.csv — hasil omit 6 baris SURPLUS
    dari kab {3521, 3519, 3522}. Committed ke repo dengan fixed content.
    JANGAN timpa surplus_deficit.csv yang lama.

Mengapa BUKAN skenario rekayasa:
    1. Ketiga kab bukan penghasil Sampang/Bangkalan — tidak ada konflik
       kepentingan antara narasi dan hasil yang diharap.
    2. Kelangkaan terjadi di beras & jagung (staple), bukan cabai — lebih
       realistis sebagai krisis pangan.
    3. Sampang dan Bangkalan tetap memiliki DEFISIT beras_premium yang besar
       (200t dan 250t) tetapi tidak ada surplus dari kab shock yang semula
       menutup mereka — supply yang tersisa harus diperebutkan.

Run:
    python benchmarks/equity_comparison_constrained.py
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
from benchmarks.equity_comparison import (
    _build_demand_tons,
    _equity_smoothed,
    _report_to_matched_tons,
    boundary_perturbation,
    compute_row,
    equity_current,
    equity_lenient,
    equity_strict,
    proportional_allocate,
    uniform_allocate,
    SAMPANG_ID,
    BANGKALAN_ID,
)

# ---------------------------------------------------------------------------
# Scenario metadata
# ---------------------------------------------------------------------------

CONSTRAINED_CSV = "surplus_deficit_constrained.csv"
SHOCK_KABS = {
    "3521": "Ngawi",
    "3519": "Madiun",
    "3522": "Bojonegoro",
}
CONSTRAINED_SURPLUS_TONS = 3962.0
CONSTRAINED_DEFICIT_TONS = 5249.0


def _run_five_strategies(surplus, deficit, logistics, weather, historical):
    """Run all 5 strategies on the given supply/deficit pool.

    Returns dict: strategy_name -> matched_tons dict.
    """
    # 1. Pure greedy
    report_greedy = run_matching(
        surplus, deficit,
        logistics=logistics,
        weather_forecasts=weather,
        historical_prices=historical,
        force_strategy="greedy",
        equity_fn=lambda _ipm: 1.0,
    )

    # 2. AgriFlow default
    report_agriflow = run_matching(
        surplus, deficit,
        logistics=logistics,
        weather_forecasts=weather,
        historical_prices=historical,
    )

    # 3. Uniform
    matched_uniform = uniform_allocate(surplus, deficit, logistics)

    # 4. Proportional
    matched_proportional = proportional_allocate(surplus, deficit, logistics)

    # 5. AgriFlow-smoothed
    report_smoothed = run_matching(
        surplus, deficit,
        logistics=logistics,
        weather_forecasts=weather,
        historical_prices=historical,
        equity_fn=_equity_smoothed,
    )

    return {
        "pure_greedy":       _report_to_matched_tons(report_greedy),
        "agriflow":          _report_to_matched_tons(report_agriflow),
        "uniform":           matched_uniform,
        "proportional":      matched_proportional,
        "agriflow_smoothed": _report_to_matched_tons(report_smoothed),
    }


def _run_sensitivity(surplus, deficit, logistics, weather, historical, demand_tons):
    """Run Action 6 sensitivity (strict/current/lenient) on a given pool."""
    sens_variants = [
        ("strict",  equity_strict,  "IPM <65->1.50, <70->1.25, <75->1.10, >=75->1.00"),
        ("current", equity_current, "IPM <68->1.30, <72->1.15, <78->1.05, >=78->1.00 [PROD]"),
        ("lenient", equity_lenient, "IPM <70->1.15, <75->1.08, <80->1.03, >=80->1.00"),
    ]
    rows = []
    for name, fn, desc in sens_variants:
        rep = run_matching(
            surplus, deficit,
            logistics=logistics,
            weather_forecasts=weather,
            historical_prices=historical,
            equity_fn=fn,
        )
        mt = _report_to_matched_tons(rep)
        rows.append({
            "variant": name,
            "desc": desc,
            "total_deficit_covered": total_deficit_covered(mt, demand_tons),
            "gini": gini(mt, demand_tons),
            "sampang": kab_fulfillment(mt, demand_tons, SAMPANG_ID),
            "bangkalan": kab_fulfillment(mt, demand_tons, BANGKALAN_ID),
            "min_fulfillment": min_fulfillment(mt, demand_tons),
        })
    return rows


def _format_table1(rows, demand_tons, caption=""):
    """Format 5-strategy rows as Markdown table lines."""
    lines = []
    if caption:
        lines.append(f"### {caption}")
        lines.append("")
    header = (
        "| Strategy          | Coverage | Gini  | Atk(0.5) | Atk(1.0) | "
        "MinFulfill | Sampang | Bangkalan |"
    )
    sep = (
        "|-------------------|----------|-------|----------|----------|"
        "-----------|---------|-----------|"
    )
    lines.append(header)
    lines.append(sep)
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
        lines.append(line)
    return lines


def _format_sensitivity(sens_rows, caption=""):
    """Format sensitivity rows as Markdown table lines."""
    lines = []
    if caption:
        lines.append(f"### {caption}")
        lines.append("")
    header = (
        "| Variant | Coverage | Gini  | MinFull | Sampang | Bangkalan | Description |"
    )
    sep = (
        "|---------|----------|-------|---------|---------|-----------|-------------|"
    )
    lines.append(header)
    lines.append(sep)
    for r in sens_rows:
        line = (
            f"| {r['variant']:<7s} "
            f"| {r['total_deficit_covered']:.4f}   "
            f"| {r['gini']:.4f}"
            f"| {r['min_fulfillment']:.4f} "
            f"| {r['sampang']:.4f} "
            f"| {r['bangkalan']:.4f}    "
            f"| {r['desc']} |"
        )
        lines.append(line)
    return lines


def main():
    print("=" * 80)
    print("  AGRIFLOW EQUITY COMPARISON — ABUNDANT vs CONSTRAINED")
    print("=" * 80)

    logistics = LogisticsContext()

    # -----------------------------------------------------------------------
    # ABUNDANT data (canonical)
    # -----------------------------------------------------------------------
    print("  [ABUNDANT] Loading canonical Jatim sample data ...")
    data_a = load_all_sample_data()
    surplus_a = data_a["surplus"]
    deficit_a = data_a["deficit"]
    weather = data_a["weather"]
    # Deliberately None. run_matching()'s 3-sigma price filter compares each node's
    # price against historical_price_stats.csv, which since commit 2819ca6 holds
    # REAL PIHPS medians and deviations. The surplus/deficit fixtures used here are
    # synthetic and were priced against the older synthetic stats, so feeding the
    # real stats makes the filter DROP fixture nodes (7 exclusions, e.g. "Kota
    # Surabaya Beras Premium @ Rp 17,000/kg") and silently changes what the five
    # strategies are even allocating. That confounds a comparison whose whole point
    # is the allocation mechanism. tests/test_constrained_scenario.py locks the same
    # golden numbers and likewise calls run_matching without historical prices; this
    # keeps the benchmark in step with the tests. The real-data path is unaffected:
    # load_real_data() produces zero anomaly exclusions, because there the prices
    # and the stats come from the same source.
    historical = None
    kabupaten_dict = data_a["kabupaten"]
    demand_tons_a = _build_demand_tons(deficit_a)

    total_surplus_a = sum(s.volume_tons for s in surplus_a)
    total_deficit_a = sum(d.volume_tons for d in deficit_a)
    print(f"  ABUNDANT  — surplus={total_surplus_a:.0f}t, deficit={total_deficit_a:.0f}t, "
          f"ratio={total_surplus_a/total_deficit_a:.3f}")

    # -----------------------------------------------------------------------
    # CONSTRAINED data (La Nina shock)
    # -----------------------------------------------------------------------
    print("  [CONSTRAINED] Loading La Nina flood shock data ...")
    print(f"    Shock: Ngawi(3521)+Madiun(3519)+Bojonegoro(3522) banjir bersamaan.")
    print(f"    Removed: beras_premium 1150t + beras_medium 2100t + jagung 1400t")
    print(f"    Fixture: sample_data/{CONSTRAINED_CSV}")
    data_c = load_all_sample_data(surplus_deficit_csv=CONSTRAINED_CSV)
    surplus_c = data_c["surplus"]
    deficit_c = data_c["deficit"]
    demand_tons_c = _build_demand_tons(deficit_c)

    total_surplus_c = sum(s.volume_tons for s in surplus_c)
    total_deficit_c = sum(d.volume_tons for d in deficit_c)
    print(f"  CONSTRAINED — surplus={total_surplus_c:.0f}t, deficit={total_deficit_c:.0f}t, "
          f"ratio={total_surplus_c/total_deficit_c:.3f}  [UNDER-SUPPLIED]")
    print()

    # -----------------------------------------------------------------------
    # Run five strategies on BOTH scenarios
    # -----------------------------------------------------------------------
    print("  Running 5 strategies x 2 scenarios (10 matching runs) ...")
    strategies_a = _run_five_strategies(surplus_a, deficit_a, logistics, weather, historical)
    print("    ABUNDANT done.")
    strategies_c = _run_five_strategies(surplus_c, deficit_c, logistics, weather, historical)
    print("    CONSTRAINED done.")
    print()

    strategy_order = ["pure_greedy", "agriflow", "uniform", "proportional", "agriflow_smoothed"]

    rows_a = [compute_row(s, strategies_a[s], demand_tons_a) for s in strategy_order]
    rows_c = [compute_row(s, strategies_c[s], demand_tons_c) for s in strategy_order]

    # -----------------------------------------------------------------------
    # Run sensitivity on BOTH scenarios
    # -----------------------------------------------------------------------
    print("  Running Action 6 sensitivity x 2 scenarios (6 matching runs) ...")
    sens_a = _run_sensitivity(surplus_a, deficit_a, logistics, weather, historical, demand_tons_a)
    print("    ABUNDANT sensitivity done.")
    sens_c = _run_sensitivity(surplus_c, deficit_c, logistics, weather, historical, demand_tons_c)
    print("    CONSTRAINED sensitivity done.")
    print()

    # -----------------------------------------------------------------------
    # Print TABLE 1A — ABUNDANT
    # -----------------------------------------------------------------------
    lines_1a = _format_table1(rows_a, demand_tons_a, caption="ABUNDANT (surplus=8612t, deficit=5249t, ratio=1.641)")
    lines_1c = _format_table1(rows_c, demand_tons_c, caption="CONSTRAINED / La Nina banjir Ngawi+Madiun+Bojonegoro (surplus=3962t, deficit=5249t, ratio=0.754)")

    print("=" * 80)
    print("  TABLE 1A — BASELINE COMPARISON (ABUNDANT scenario)")
    print("=" * 80)
    for line in lines_1a:
        print("  " + line)
    print()

    print("=" * 80)
    print("  TABLE 1C — BASELINE COMPARISON (CONSTRAINED scenario)")
    print("=" * 80)
    for line in lines_1c:
        print("  " + line)
    print()

    # -----------------------------------------------------------------------
    # Print TABLE 2 — Sensitivity
    # -----------------------------------------------------------------------
    lines_2a = _format_sensitivity(sens_a, caption="Sensitivity ABUNDANT")
    lines_2c = _format_sensitivity(sens_c, caption="Sensitivity CONSTRAINED")

    print("=" * 80)
    print("  TABLE 2C — ACTION 6 SENSITIVITY (CONSTRAINED scenario)")
    print("  Note: ABUNDANT sensitivity is degenerate (all 1.0000 for Sampang/Bangkalan).")
    print("  CONSTRAINED sensitivity should show differentiation.")
    print("=" * 80)
    for line in lines_2c:
        print("  " + line)
    print()

    # -----------------------------------------------------------------------
    # Boundary perturbation (same kab population, scenario-independent)
    # -----------------------------------------------------------------------
    perturb = boundary_perturbation(kabupaten_dict)
    print("=" * 80)
    print("  BOUNDARY PERTURBATION (unchanged — same 38 Jatim kabs)")
    print("=" * 80)
    print("  | Threshold shift | Kabs changing tier |")
    print("  |-----------------|---------------------|")
    for delta in (-2.0, -1.0, +1.0, +2.0):
        label = f"{delta:+.0f} pts"
        print(f"  | {label:<15s} | {perturb[delta]:2d}                  |")
    print()

    # -----------------------------------------------------------------------
    # ORDERING CHECKS — CONSTRAINED (where the equity story plays out)
    # -----------------------------------------------------------------------
    print("  ORDERING CHECKS — CONSTRAINED scenario:")
    check = lambda ok, msg: print(f"  {'PASS' if ok else 'FAIL (!) '} {msg}")

    g_cov = rows_c[0]["total_deficit_covered"]
    a_cov = rows_c[1]["total_deficit_covered"]
    g_gini = rows_c[0]["gini"]
    a_gini = rows_c[1]["gini"]
    u_gini = rows_c[2]["gini"]
    a_min = rows_c[1]["min_fulfillment"]
    g_min = rows_c[0]["min_fulfillment"]
    a_samp = rows_c[1]["sampang"]
    g_samp = rows_c[0]["sampang"]
    a_bang = rows_c[1]["bangkalan"]
    g_bang = rows_c[0]["bangkalan"]
    u_samp = rows_c[2]["sampang"]

    # Gini sanity check: uniform ~0 even in constrained
    check(u_gini < 0.05,
          f"uniform Gini ({u_gini:.4f}) < 0.05 [sanity: formula correct in constrained]")
    check(g_cov >= a_cov - 1e-9,
          f"greedy coverage ({g_cov:.4f}) >= agriflow ({a_cov:.4f}) [efficiency frontier]")
    check(a_gini <= g_gini + 1e-6,
          f"agriflow Gini ({a_gini:.4f}) <= greedy Gini ({g_gini:.4f}) [equity boost visible]")
    check(a_samp >= g_samp - 1e-9,
          f"Sampang: agriflow ({a_samp:.4f}) >= greedy ({g_samp:.4f}) [1.30x boost works]")
    check(a_bang >= g_bang - 1e-9,
          f"Bangkalan: agriflow ({a_bang:.4f}) >= greedy ({g_bang:.4f}) [1.30x boost works]")
    check(a_min >= g_min - 1e-9,
          f"agriflow min_fulfillment ({a_min:.4f}) >= greedy ({g_min:.4f}) [leximin better]")

    # Sensitivity: strict > lenient for Sampang under constrained
    s_strict_samp = sens_c[0]["sampang"]
    s_lenient_samp = sens_c[2]["sampang"]
    sens_degenerate = abs(s_strict_samp - s_lenient_samp) < 1e-6
    check(s_strict_samp >= s_lenient_samp - 1e-9,
          f"strict Sampang ({s_strict_samp:.4f}) >= lenient ({s_lenient_samp:.4f})")
    if sens_degenerate:
        print("  !! SENSITIVITY STILL DEGENERATE for Sampang — equity mechanism may need review")
    else:
        print(f"  ** Sensitivity spread: strict-lenient Sampang delta = "
              f"{s_strict_samp - s_lenient_samp:+.4f} [non-degenerate]")

    # Summary interpretation
    print()
    print("  INTERPRETATION:")
    if a_samp > g_samp + 1e-4:
        print(f"  + AgriFlow protects Sampang (+{(a_samp-g_samp)*100:.1f}pp vs greedy)")
    else:
        print(f"  ~ Sampang: AgriFlow = greedy (delta={a_samp-g_samp:+.4f})")
    if a_bang > g_bang + 1e-4:
        print(f"  + AgriFlow protects Bangkalan (+{(a_bang-g_bang)*100:.1f}pp vs greedy)")
    else:
        print(f"  ~ Bangkalan: AgriFlow = greedy (delta={a_bang-g_bang:+.4f})")
    if a_gini < g_gini - 1e-4:
        print(f"  + AgriFlow Gini lower than greedy ({a_gini:.4f} vs {g_gini:.4f}): equity visible")
    else:
        print(f"  ~ Gini: AgriFlow ({a_gini:.4f}) vs greedy ({g_gini:.4f}) — marginal or no improvement")
    cost_pp = (g_cov - a_cov) * 100
    if cost_pp > 0.05:
        print(f"  - Coverage cost: AgriFlow sacrifices {cost_pp:.1f}pp aggregate coverage for equity")
    else:
        print(f"  ~ Coverage cost: negligible ({cost_pp:.2f}pp)")
    print()

    # -----------------------------------------------------------------------
    # WRITE OUTPUT
    # -----------------------------------------------------------------------
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "equity_comparison_constrained.md")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# AgriFlow Equity Comparison — ABUNDANT vs CONSTRAINED\n\n")
        f.write("Generated by `benchmarks/equity_comparison_constrained.py`.\n\n")
        f.write("## Scenario: La Nina Supply Shock (CONSTRAINED)\n\n")
        f.write("**Narasi:** La Nina banjir besar menghantam tiga sentra beras utama Jatim\n")
        f.write("bagian barat — Ngawi (3521), Madiun (3519), Bojonegoro (3522) — secara\n")
        f.write("bersamaan. Ketiga kab berada di dataran rendah lembah Bengawan Solo dan\n")
        f.write("anak sungainya; pola banjir simultan terdokumentasi pada La Nina 2010,\n")
        f.write("2020–21, dan 2022–23.\n\n")
        f.write("**Dampak:** 6 surplus rows dihapus:\n\n")
        f.write("| Kab | Nama | Komoditas | Volume (t) |\n")
        f.write("|-----|------|-----------|------------|\n")
        f.write("| 3521 | Ngawi | beras_premium | 500 |\n")
        f.write("| 3521 | Ngawi | beras_medium | 900 |\n")
        f.write("| 3521 | Ngawi | jagung | 600 |\n")
        f.write("| 3519 | Madiun | beras_medium | 1200 |\n")
        f.write("| 3522 | Bojonegoro | beras_premium | 650 |\n")
        f.write("| 3522 | Bojonegoro | jagung | 800 |\n")
        f.write("| **Total** | | | **4650** |\n\n")
        f.write("**Arithmetic:**\n\n")
        f.write("| Scenario | Surplus (t) | Deficit (t) | Ratio |\n")
        f.write("|----------|-------------|-------------|-------|\n")
        f.write(f"| ABUNDANT    | 8612 | 5249 | 1.641 (over-supplied) |\n")
        f.write(f"| CONSTRAINED | 3962 | 5249 | 0.754 (under-supplied by 32.5%) |\n\n")
        f.write("Fixture: `sample_data/surplus_deficit_constrained.csv` (committed).\n\n")
        f.write("---\n\n")
        f.write("## Table 1A — Baseline Comparison: ABUNDANT\n\n")
        f.write("Coverage = volume-weighted tons fulfilled / tons demanded.  \n")
        f.write("Gini / Atkinson = weighted by demand volume; lower = more equitable.  \n")
        f.write("MinFulfill = fulfillment ratio of worst-served demand node.  \n")
        f.write("Sampang=3527 (IPM 66.72), Bangkalan=3526 (IPM 67.70).  \n\n")
        for line in lines_1a:
            f.write(line + "\n")
        f.write("\n")
        f.write("## Table 1C — Baseline Comparison: CONSTRAINED\n\n")
        f.write("Same metrics. Under supply shortage, equity tradeoffs become observable.\n\n")
        for line in lines_1c:
            f.write(line + "\n")
        f.write("\n")
        f.write("## Table 2A — Sensitivity: ABUNDANT (degenerate — included for completeness)\n\n")
        for line in lines_2a:
            f.write(line + "\n")
        f.write("\n")
        f.write("## Table 2C — Sensitivity: CONSTRAINED\n\n")
        f.write("`current` delegates to `equity_multiplier_value` — single source of truth.\n\n")
        for line in lines_2c:
            f.write(line + "\n")
        f.write("\n")
        f.write("## Boundary Perturbation\n\n")
        f.write("Same 38 Jatim kabs in both scenarios. Scenario-independent.\n\n")
        f.write("| Threshold shift | Kabs changing tier |\n")
        f.write("|-----------------|---------------------|\n")
        for delta in (-2.0, -1.0, +1.0, +2.0):
            label = f"{delta:+.0f} pts"
            f.write(f"| {label:<15s} | {perturb[delta]:2d}                  |\n")
        f.write("\n")

    print(f"  Tables written to: {output_path}")
    print("=" * 80)
    print("  DONE.")
    print("=" * 80)


if __name__ == "__main__":
    main()
