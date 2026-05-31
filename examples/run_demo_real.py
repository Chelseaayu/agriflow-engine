"""
AgriFlow Matching Engine — Demo DATA REAL BPS Jawa Timur 2022
=============================================================

Run: python examples/run_demo_real.py

Data sumber: sample_data/surplus_deficit_real.csv
  - 228 baris, 6 komoditas @ 2022 (per-kab BPS)
  - beras_premium, beras_medium, cabai_merah, cabai_rawit,
    bawang_merah, bawang_putih
  - TIDAK menggunakan data sintetis; default surplus_deficit.csv tidak diubah.

Output:
  - Header jelas "DATA REAL — BPS Jawa Timur 2022"
  - Jumlah match, top matches, total volume & nilai ekonomi
  - External opportunities / unmatched (termasuk bawang_putih all-deficit)
"""

import sys
import os

# Force UTF-8 stdout/stderr di Windows (default cp1252 crash saat print "->", "*", "!").
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

# Add project root ke sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from matching_engine import run_matching, LogisticsContext
from sample_data import load_real_data


def format_idr(amount: float) -> str:
    return f"Rp {amount:,.0f}".replace(",", ".")


def print_match_table(matches, limit=15):
    if not matches:
        print("  (tidak ada match)")
        return
    header = (
        f"{'#':>3} {'Surplus (asal)':<22} -> {'Deficit (tujuan)':<22} "
        f"{'Komoditas':<18} {'Vol(t)':>8} {'Dist(km)':>8} "
        f"{'Score':>6} {'Conf':<6}"
    )
    print(header)
    print("-" * len(header))
    for i, m in enumerate(matches[:limit], 1):
        print(
            f"{i:>3} {m.surplus.kabupaten.nama:<22} -> "
            f"{m.deficit.kabupaten.nama:<22} "
            f"{m.surplus.commodity.nama[:18]:<18} "
            f"{m.matched_volume_tons:>8,.1f} "
            f"{m.distance_km:>8.0f} "
            f"{m.final_score:>6.1f} "
            f"{m.confidence.value:<6}"
        )
        if m.flags:
            print(f"      flags: {', '.join(m.flags)}")
        if m.notes:
            print(f"      note:  {m.notes}")


def main():
    print("=" * 80)
    print("  AgriFlow Matching Engine v9.0")
    print("  DATA REAL -- BPS Jawa Timur 2022")
    print("  6 Komoditas: beras_premium, beras_medium, cabai_merah,")
    print("               cabai_rawit, bawang_merah, bawang_putih")
    print("=" * 80)
    print()

    # 1. Load real data (BPS Jatim 2022 — 228 baris, 6 komoditas)
    print("-> Loading data real: sample_data/surplus_deficit_real.csv")
    data = load_real_data()
    surplus = data["surplus"]
    deficit = data["deficit"]
    weather = data["weather"]
    historical = data["historical_prices"]

    surplus_by_comm = {}
    deficit_by_comm = {}
    for s in surplus:
        surplus_by_comm.setdefault(s.commodity.code, []).append(s)
    for d in deficit:
        deficit_by_comm.setdefault(d.commodity.code, []).append(d)

    print(f"   Surplus nodes:  {len(surplus)}")
    print(f"   Deficit nodes:  {len(deficit)}")
    print(f"   Weather routes: {len(weather)}")
    print()
    print("   Breakdown per komoditas:")
    all_codes = sorted(set(list(surplus_by_comm.keys()) + list(deficit_by_comm.keys())))
    for code in all_codes:
        ns = len(surplus_by_comm.get(code, []))
        nd = len(deficit_by_comm.get(code, []))
        total_s = sum(x.volume_tons for x in surplus_by_comm.get(code, []))
        total_d = sum(x.volume_tons for x in deficit_by_comm.get(code, []))
        tag = " [ALL DEFICIT - no domestic surplus]" if ns == 0 else ""
        print(f"     {code:<22}  surplus={ns:2d} nodes ({total_s:>12,.0f} t)  "
              f"deficit={nd:2d} nodes ({total_d:>12,.0f} t){tag}")
    print()

    # 2. Setup logistics context (solar bersubsidi, normal conditions)
    logistics = LogisticsContext(
        bbm_price_idr_per_liter=10000,
        bbm_price_baseline=10000,
        truck_consumption_km_per_liter=4.0,
        avg_speed_km_per_hour=60,
        transit_hours_per_day=8,
    )

    # 3. Run matching
    print("-> Running matching engine pada data real...")
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
    print("  HASIL MATCHING -- DATA REAL BPS JAWA TIMUR 2022")
    print("=" * 80)
    print()
    meta = report.run_metadata
    print(f"Latency:                   {meta['latency_ms']} ms (target <500ms)")
    print(f"Total matches:             {meta['total_matches']}")
    print(f"  Tier1-Tier1 matches:     {meta['tier1_tier1_matches']}")
    print(f"  Cross/Tier2 matches:     {meta['cross_or_tier2_matches']}")
    print(f"Candidate pairs evaluated: {meta['candidate_pairs_evaluated']}")
    print(f"Ramadan mode:              {meta['ramadan_active']}")
    print(f"Import policy:             {meta['import_policy_active']}")
    print(f"Stale data nodes:          {meta['stale_data_count']}")
    print()

    print(f"-> TOP {min(15, meta['total_matches'])} MATCHES (sorted by FinalScore desc)")
    print("-" * 80)
    print_match_table(report.matches, limit=15)
    print()

    # 5. Warnings dari engine
    if report.warnings:
        print(f"-> WARNINGS ({len(report.warnings)})")
        print("-" * 80)
        for w in report.warnings:
            print(f"  ! {w}")
        print()

    # 6. External opportunities (termasuk bawang_putih all-deficit)
    if report.external_opportunities:
        print(f"-> EXTERNAL OPPORTUNITIES / SARAN IMPOR ({len(report.external_opportunities)})")
        print("-" * 80)
        for opp in report.external_opportunities:
            print(f"  * {opp}")
        print()
        # Highlight bawang_putih specifically
        bp_opps = [o for o in report.external_opportunities if "bawang_putih" in o]
        if bp_opps:
            print("  [NOTE] bawang_putih: Jawa Timur 2022 tidak punya surplus domestik.")
            print("         Semua 38 kabupaten/kota DEFICIT (produksi ~855 ton vs")
            print("         konsumsi ~80.640 ton). Engine menghasilkan ZERO matches")
            print("         untuk bawang_putih — sudah ditangani gracefully sebagai")
            print("         external opportunity (saran: impor Jawa Tengah/luar Jatim).")
            print()

    # 7. Unmatched surplus
    if report.unmatched_surplus:
        print(f"-> UNMATCHED SURPLUS ({len(report.unmatched_surplus)} nodes)")
        print("-" * 80)
        for s in report.unmatched_surplus[:8]:
            print(f"  {s.kabupaten.nama:<22} {s.commodity.nama:<25} "
                  f"{s.volume_tons:>10,.1f} t @ {format_idr(s.price_per_kg)}/kg")
        if len(report.unmatched_surplus) > 8:
            print(f"  ... +{len(report.unmatched_surplus) - 8} lainnya")
        print()

    # 8. Unmatched deficit
    if report.unmatched_deficit:
        print(f"-> UNMATCHED DEFICIT ({len(report.unmatched_deficit)} nodes)")
        print("-" * 80)

        # Group bawang_putih separately for clarity
        bp_def = [d for d in report.unmatched_deficit if d.commodity.code == "bawang_putih"]
        other_def = [d for d in report.unmatched_deficit if d.commodity.code != "bawang_putih"]

        for d in other_def[:5]:
            print(f"  {d.kabupaten.nama:<22} {d.commodity.nama:<25} "
                  f"{d.volume_tons:>10,.1f} t @ {format_idr(d.price_per_kg)}/kg")
        if len(other_def) > 5:
            print(f"  ... +{len(other_def) - 5} other unmatched deficit nodes")

        if bp_def:
            total_bp = sum(d.volume_tons for d in bp_def)
            print(f"\n  bawang_putih (all-deficit): {len(bp_def)} nodes, "
                  f"{total_bp:,.0f} ton total unmatched")
            print(f"  Saran: impor dari Jawa Tengah (Tegal/Brebes) atau luar Jatim.")
        print()

    # 9. Estimasi dampak ekonomi
    total_value = sum(
        m.matched_volume_tons * 1000 * (m.deficit.price_per_kg - m.surplus.price_per_kg)
        for m in report.matches
        if m.deficit.price_per_kg > m.surplus.price_per_kg
    )
    total_volume = sum(m.matched_volume_tons for m in report.matches)

    print("=" * 80)
    print("  ESTIMASI DAMPAK EKONOMI -- DATA REAL BPS JAWA TIMUR 2022")
    print("=" * 80)
    print(f"Total volume matched:      {total_volume:>12,.1f} ton")
    print(f"Gross arbitrage value:     {format_idr(total_value):>18s}")
    print(f"  (selisih harga x volume, sebelum biaya logistik)")
    print()

    # 10. Ringkasan per komoditas (hasil matching)
    print("-> RINGKASAN PER KOMODITAS")
    print("-" * 80)
    match_by_comm = {}
    for m in report.matches:
        code = m.surplus.commodity.code
        if code not in match_by_comm:
            match_by_comm[code] = {"count": 0, "volume": 0.0}
        match_by_comm[code]["count"] += 1
        match_by_comm[code]["volume"] += m.matched_volume_tons

    for code in all_codes:
        if code in match_by_comm:
            d = match_by_comm[code]
            print(f"  {code:<22}  {d['count']:3d} matches, {d['volume']:>12,.1f} ton matched")
        elif code == "bawang_putih":
            # Two constraints compound: no domestic surplus + price anomaly exclusion
            print(f"  {code:<22}    0 matches (no domestic surplus; real price Rp 20,750"
                  f" vs synth median Rp 40,000 => z~3.2σ → price anomaly exclusion)")
        elif code in ("cabai_merah", "cabai_rawit"):
            # Real CSV sets harvest_age_days=28 uniformly; cabai max_fresh_age_days=5
            print(f"  {code:<22}    0 matches (harvest_age_days=28 > max_fresh_age_days=5"
                  f" → Layer 1 freshness constraint; real-time data would use age=0..2)")
        else:
            print(f"  {code:<22}    0 matches")
    print()

    # 11. Constraint summary — honest reporting
    print("-> CONSTRAINT NOTES (DATA REAL vs ENGINE DEFAULTS)")
    print("-" * 80)
    print("  [1] bawang_putih: Jatim 2022 produksi ~855 ton, konsumsi ~80.640 ton.")
    print("      Semua 38 kab DEFICIT. Tidak ada surplus domestik.")
    print("      TAMBAHAN: real PIHPS 2022 price (Rp 20.750) vs historical_price_stats")
    print("      sintetis (median Rp 40.000, std 6.000) → z=3.21 → price anomaly excludes")
    print("      semua 38 deficit nodes. Engine graceful: 38 warnings, 0 matches, 0 crash.")
    print()
    print("  [2] cabai_merah, cabai_rawit: harvest_age_days=28 di real CSV (uniform")
    print("      untuk semua SURPLUS). Constraint max_fresh_age_days=5 (cabai sangat")
    print("      perishable). Layer 1 rejects semua pair → 0 candidates → 0 matches.")
    print("      Di produksi: harvest_age harus dari scraper real-time (0..2 hari),")
    print("      bukan nilai statis. Unmatched deficit (39 nodes) mencerminkan hal ini.")
    print()
    print("  [3] Gross arbitrage = 0: surplus dan deficit dalam komoditas yang sama")
    print("      menggunakan harga referensi yang identik (PIHPS/BPS 2022 uniform).")
    print("      Dalam produksi, harga akan berbeda antar kabupaten (spread arbitrage")
    print("      muncul dari variasi harga lokal BPS per kab).")
    print()


if __name__ == "__main__":
    main()
