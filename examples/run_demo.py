"""
AgriFlow Matching Engine — Demo End-to-End
============================================

Run: python examples/run_demo.py

Output:
    - Top 10 matches dengan scoring breakdown
    - Unmatched supply/deficit
    - External opportunities
    - Latency metrics
"""

import sys
import os

# Force UTF-8 stdout/stderr di Windows (default cp1252 crash saat print "→", "★", "⚠").
# Tanpa ini demo gagal di console Windows fresh — first-impression killer untuk juri.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

# Add parent ke path supaya bisa import matching_engine & sample_data
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from matching_engine import run_matching, LogisticsContext
from sample_data import load_all_sample_data


def format_idr(amount: float) -> str:
    return f"Rp {amount:,.0f}".replace(",", ".")


def print_match_table(matches, limit=15):
    if not matches:
        print("  (tidak ada match)")
        return
    header = (f"{'#':>3} {'Surplus':<22} → {'Deficit':<22} "
              f"{'Komoditas':<18} {'Vol(t)':>6} {'Dist':>5} "
              f"{'Base':>5} {'Eq':>5} {'Final':>6} {'Conf':<6}")
    print(header)
    print("-" * len(header))
    for i, m in enumerate(matches[:limit], 1):
        print(
            f"{i:>3} {m.surplus.kabupaten.nama:<22} → "
            f"{m.deficit.kabupaten.nama:<22} "
            f"{m.surplus.commodity.nama[:18]:<18} "
            f"{m.matched_volume_tons:>6.1f} "
            f"{m.distance_km:>5.0f} "
            f"{m.base_score:>5.1f} "
            f"{m.equity_multiplier:>5.2f} "
            f"{m.final_score:>6.1f} "
            f"{m.confidence.value:<6}"
        )
        if m.flags:
            print(f"      flags: {', '.join(m.flags)}")
        if m.notes:
            print(f"      note:  {m.notes}")


def main():
    print("=" * 80)
    print("  AgriFlow Matching Engine v9.0 — Demo End-to-End")
    print("=" * 80)
    print()

    # 1. Load sample data
    print("→ Loading sample data 38 kabupaten Jatim × 19 komoditas...")
    data = load_all_sample_data()
    surplus = data["surplus"]
    deficit = data["deficit"]
    weather = data["weather"]
    historical = data["historical_prices"]
    print(f"   Surplus nodes:  {len(surplus)}")
    print(f"   Deficit nodes:  {len(deficit)}")
    print(f"   Weather routes: {len(weather)}")
    print(f"   Historical:     {len(historical)} komoditas")
    print()

    # 2. Setup logistics context
    logistics = LogisticsContext(
        bbm_price_idr_per_liter=10000,    # solar bersubsidi
        bbm_price_baseline=10000,
        truck_consumption_km_per_liter=4.0,
        avg_speed_km_per_hour=60,
        transit_hours_per_day=8,
    )

    # 3. Run matching
    print("→ Running matching engine...")
    report = run_matching(
        surplus_nodes=surplus,
        deficit_nodes=deficit,
        logistics=logistics,
        weather_forecasts=weather,
        historical_prices=historical,
    )

    # 4. Print results
    print()
    print("=" * 80)
    print("  HASIL MATCHING")
    print("=" * 80)
    print()
    meta = report.run_metadata
    print(f"Latency: {meta['latency_ms']} ms (target <500ms)")
    print(f"Total matches:           {meta['total_matches']}")
    print(f"  Tier1↔Tier1:           {meta['tier1_tier1_matches']}")
    print(f"  Cross-tier / Tier2:    {meta['cross_or_tier2_matches']}")
    print(f"Candidate pairs evaluated: {meta['candidate_pairs_evaluated']}")
    print(f"Ramadan mode:    {meta['ramadan_active']}")
    print(f"Import policy:   {meta['import_policy_active']}")
    print(f"BBM change:      {meta['bbm_change_pct'] * 100:.1f}%")
    print()

    print("→ TOP 15 MATCHES (sorted by FinalScore desc)")
    print("-" * 80)
    print_match_table(report.matches, limit=15)
    print()

    if report.warnings:
        print("→ WARNINGS")
        print("-" * 80)
        for w in report.warnings:
            print(f"  ⚠ {w}")
        print()

    if report.external_opportunities:
        print("→ EXTERNAL OPPORTUNITIES")
        print("-" * 80)
        for opp in report.external_opportunities:
            print(f"  ★ {opp}")
        print()

    if report.unmatched_surplus:
        print(f"→ UNMATCHED SURPLUS ({len(report.unmatched_surplus)} nodes)")
        print("-" * 80)
        for s in report.unmatched_surplus[:5]:
            print(f"  {s.kabupaten.nama:20s} {s.commodity.nama:25s} "
                  f"{s.volume_tons:>6.1f} ton @ {format_idr(s.price_per_kg)}/kg")
        if len(report.unmatched_surplus) > 5:
            print(f"  ... +{len(report.unmatched_surplus) - 5} lainnya")
        print()

    if report.unmatched_deficit:
        print(f"→ UNMATCHED DEFICIT ({len(report.unmatched_deficit)} nodes)")
        print("-" * 80)
        for d in report.unmatched_deficit[:5]:
            print(f"  {d.kabupaten.nama:20s} {d.commodity.nama:25s} "
                  f"{d.volume_tons:>6.1f} ton @ {format_idr(d.price_per_kg)}/kg")
        if len(report.unmatched_deficit) > 5:
            print(f"  ... +{len(report.unmatched_deficit) - 5} lainnya")
        print()

    # 5. Estimasi dampak ekonomi
    total_value = sum(
        m.matched_volume_tons * 1000 * (m.deficit.price_per_kg - m.surplus.price_per_kg)
        for m in report.matches
    )
    total_volume = sum(m.matched_volume_tons for m in report.matches)
    print("=" * 80)
    print("  ESTIMASI DAMPAK")
    print("=" * 80)
    print(f"Total volume matched:     {total_volume:>10,.1f} ton")
    print(f"Gross arbitrage value:    {format_idr(total_value):>15s}")
    print(f"  (selisih harga × vol, sebelum biaya logistik)")
    print()


if __name__ == "__main__":
    main()
