"""
analysis/run_anomaly_report.py  --  Price anomaly report for AgriFlow.

Usage (from project root):
    python analysis/run_anomaly_report.py
    python analysis/run_anomaly_report.py --top 20 --k 2.5
    python analysis/run_anomaly_report.py --window 14 --k 3.0 --commodity cabai_rawit
    python analysis/run_anomaly_report.py --compare   # show BEFORE vs AFTER flag counts

Method v2: S-H-ESD (Seasonal-Hybrid ESD).
  v1 was rolling-median + MAD on raw prices; this is deseasonalise first,
  then MAD on residuals, with persistence and low-vol gates.
  Result: ~70 % reduction in flag count (14,261 -> 4,192 on 2021-2025 Jatim data).

No external API calls; fully offline.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Force UTF-8 stdout/stderr on Windows (default cp1252 breaks "Rp", arrows, etc.)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

# Allow running from project root without pip install
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from analysis.price_anomaly import scan_all, CITY_NAMES

PRICE_DIR = _ROOT / "sample_data" / "price_history"

COMMODITY_LABELS = {
    "cabai_rawit":  "Cabai Rawit",
    "bawang_merah": "Bawang Merah",
    "bawang_putih": "Bawang Putih",
    "daging_ayam":  "Daging Ayam",
    "telur_ayam":   "Telur Ayam",
    "beras_medium": "Beras Medium",
    "beras_premium":"Beras Premium",
}


def _fmt_price(p: float) -> str:
    return f"Rp {p:,.0f}/kg"


def _run_v1_count() -> int:
    """
    Reproduce the v1 (raw-price rolling-MAD) flag count for BEFORE/AFTER comparison.
    Uses the same k=3.0, window=30 as the default.
    """
    from analysis.price_anomaly import _load_all_rows
    import numpy as np

    series_map = _load_all_rows(PRICE_DIR)
    total = 0
    window = 30
    k = 3.0

    for (commodity, city), series in series_map.items():
        if len(series) < window:
            continue
        prices = np.array([p for _, p in series], dtype=float)
        n = len(prices)
        for t in range(window - 1, n):
            w = prices[t - window + 1 : t + 1]
            roll_med = float(np.median(w))
            mad = float(np.median(np.abs(w - roll_med)))
            if mad == 0.0:
                if prices[t] != roll_med:
                    total += 1
                continue
            if abs(prices[t] - roll_med) > k * 1.4826 * mad:
                total += 1

    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="AgriFlow price anomaly report (S-H-ESD v2)")
    parser.add_argument("--top",      type=int,   default=15,   help="Top N to show (default 15)")
    parser.add_argument("--window",   type=int,   default=30,   help="Rolling window size (default 30)")
    parser.add_argument("--k",        type=float, default=3.0,  help="MAD sensitivity k (default 3.0)")
    parser.add_argument("--persist",  type=int,   default=2,    help="Persistence threshold (default 2)")
    parser.add_argument("--commodity", type=str,  default=None, help="Filter to one commodity code")
    parser.add_argument("--compare",  action="store_true",
                        help="Show BEFORE (v1 raw-price MAD) vs AFTER (S-H-ESD v2) counts")
    args = parser.parse_args()

    print()
    print("=" * 72)
    print("  AgriFlow -- Deteksi Anomali Harga (S-H-ESD v2, PIHPS Jatim 2021-2025)")
    print("=" * 72)
    print(f"  Data      : {PRICE_DIR}")
    print(f"  Window    : {args.window} observations")
    print(f"  Threshold : k={args.k}  (|dev| > {args.k} * 1.4826 * MAD on RESIDUAL)")
    print(f"  Persist   : >= {args.persist} consecutive flagged observations")
    print(f"  Method    : S-H-ESD -- deseasonalise, then robust MAD on residual")
    print(f"              (Hochenbaum/Vallis/Kejariwal arXiv:1704.07706)")
    print(f"              NOT 'AI'; interpretable statistical detector")
    print()

    # BEFORE/AFTER comparison
    if args.compare:
        print("  Computing BEFORE count (v1 rolling-MAD on raw prices) ...", end=" ", flush=True)
        before_count = _run_v1_count()
        print(f"done. {before_count:,} flags.")

    print("  Running S-H-ESD v2 ...", end=" ", flush=True)
    anomalies = scan_all(
        PRICE_DIR,
        window=args.window,
        k=args.k,
        persist=args.persist,
    )
    after_count = len(anomalies)
    print(f"done. {after_count:,} anomaly points detected.")

    if args.compare:
        reduction = (before_count - after_count) / before_count * 100
        print()
        print("  BEFORE vs AFTER:")
        print(f"    v1 (raw-price rolling-MAD)  : {before_count:>7,} flags")
        print(f"    v2 (S-H-ESD, deseasonalised): {after_count:>7,} flags")
        print(f"    Reduction                   : {reduction:>6.1f} %")

    print()

    if args.commodity:
        anomalies = [a for a in anomalies if a["commodity_code"] == args.commodity]
        print(f"  Filtered to '{args.commodity}': {len(anomalies):,} anomalies.")
        print()

    if not anomalies:
        print("  No anomalies found for the given filters.")
        return

    top = anomalies[: args.top]

    print(f"  Top {len(top)} anomalies ranked by score (highest first):")
    print()
    print(f"  {'#':>3}  {'Date':<12}  {'Type':<6}  {'Commodity':<15}  {'Kota':<20}"
          f"  {'Price':>14}  {'Dev%':>8}  {'Score':>7}  {'Persist':<8}")
    print("  " + "-" * 106)

    for i, a in enumerate(top, 1):
        city_name = CITY_NAMES.get(a["city_id"], a["city_id"])
        comm_label = COMMODITY_LABELS.get(a["commodity_code"], a["commodity_code"])
        sign = "+" if a["deviation_pct"] > 0 else ""
        persist_marker = "YES" if a["persistent"] else "no"
        print(
            f"  {i:>3}  {str(a['date']):<12}  {a['type']:<6}  {comm_label:<15}  "
            f"{city_name:<20}  {_fmt_price(a['price']):>14}  "
            f"{sign}{a['deviation_pct']:>6.1f}%  {a['score']:>7.2f}  {persist_marker:<8}"
        )

    print()
    print("  Catatan keterbatasan (S-H-ESD v2):")
    print("  - Seasonal komponen: monthly median -- Ramadan (Hijri) drifts ~11 hr/thn;")
    print("    spike Ramadan di tanggal masehi tak biasa masih bisa muncul parsial.")
    print("  - Trend window = rolling median; lag 15-obs saat price-regime shift cepat.")
    print("  - Persist filter = consecutive observations, bukan hari kalender.")
    print("    Untuk data mingguan, persist=2 = '2 minggu berturut-turut'.")
    print("  - beras_medium/premium: rata-rata 2 sub-grade PIHPS; anomali sedikit")
    print("    konservatif dibanding single-grade.")
    print()

    # Summary by commodity
    from collections import Counter
    by_comm = Counter(a["commodity_code"] for a in anomalies)
    print("  Total anomalies per commodity (semua, bukan hanya top N):")
    for comm, count in by_comm.most_common():
        label = COMMODITY_LABELS.get(comm, comm)
        persistent_count = sum(1 for a in anomalies if a["commodity_code"] == comm and a["persistent"])
        print(f"    {label:<20} : {count:>5} points  ({persistent_count} persistent)")
    print()
    print("=" * 72)


if __name__ == "__main__":
    main()
