"""
AgriFlow Matching Engine — Latency Benchmark
=============================================

Measure end-to-end latency dengan multiple konfigurasi untuk memvalidasi
klaim "<500ms p99 untuk 38 kab × 19 komoditas" (Section 5.5.4).

Run:
    python benchmarks/latency.py

Output:
    Tabel p50/p95/p99/max latency untuk:
        - Sample data current (40 supply × 33 deficit)
        - Stress: synthetic 38 kab × 19 komoditas full
        - Stress: 100 supply × 100 deficit (large)
"""
from __future__ import annotations
import os
import statistics
import sys
import time
from datetime import datetime

# Force UTF-8 stdio di Windows.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

# Add project root ke path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from matching_engine import (
    Commodity, DemandNode, Kabupaten, LogisticsContext, SupplyNode, Tier,
    run_matching,
)
from sample_data import load_all_sample_data
from sample_data.generate_sample_data import KABUPATEN_DATA, KOMODITAS_DATA


def percentile(data, p):
    s = sorted(data)
    k = (len(s) - 1) * p
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def bench_one(label: str, supply, demand, weather=None, historical=None,
              warmup: int = 5, iterations: int = 100) -> dict:
    logistics = LogisticsContext()
    # Warmup
    for _ in range(warmup):
        run_matching(supply, demand, logistics=logistics,
                     weather_forecasts=weather, historical_prices=historical)
    # Measure
    samples = []
    for _ in range(iterations):
        t = time.perf_counter()
        run_matching(supply, demand, logistics=logistics,
                     weather_forecasts=weather, historical_prices=historical)
        samples.append((time.perf_counter() - t) * 1000)
    return {
        "label": label,
        "n_supply": len(supply),
        "n_demand": len(demand),
        "iterations": iterations,
        "p50_ms": percentile(samples, 0.50),
        "p95_ms": percentile(samples, 0.95),
        "p99_ms": percentile(samples, 0.99),
        "min_ms": min(samples),
        "max_ms": max(samples),
        "mean_ms": statistics.mean(samples),
    }


def make_synthetic_full_jatim():
    """38 kab × 19 komoditas: setengah surplus, setengah deficit per komoditas."""
    kabs = []
    for kid, nama, lat, lon, ipm, pop, tier_s in KABUPATEN_DATA:
        kabs.append(Kabupaten(
            id=kid, nama=nama, latitude=lat, longitude=lon, ipm=ipm,
            tier=Tier.HIGH if tier_s == "TIER_1_HIGH" else Tier.MEDIUM,
            population=pop,
        ))
    komos = [
        Commodity(code=c, nama=n, max_distance_km=md, min_viable_tons=mv,
                  max_fresh_age_days=mf)
        for c, n, md, mv, mf, _baseline in KOMODITAS_DATA
    ]
    surplus, deficit = [], []
    for komo in komos:
        for i, kab in enumerate(kabs):
            if i % 2 == 0:
                surplus.append(SupplyNode(
                    kabupaten=kab, commodity=komo,
                    volume_tons=max(komo.min_viable_tons * 5, 20.0),
                    price_per_kg=30000, harvest_age_days=1,
                ))
            else:
                deficit.append(DemandNode(
                    kabupaten=kab, commodity=komo,
                    volume_tons=max(komo.min_viable_tons * 4, 15.0),
                    price_per_kg=50000,
                ))
    return surplus, deficit


def make_synthetic_large(n_supply: int = 100, n_demand: int = 100):
    """Stress test: scale beyond Jatim (project to national scale)."""
    s, d = make_synthetic_full_jatim()
    # Pad dengan duplikat (anggap nasional projection)
    while len(s) < n_supply:
        s.extend(s[:n_supply - len(s)])
    while len(d) < n_demand:
        d.extend(d[:n_demand - len(d)])
    return s[:n_supply], d[:n_demand]


def print_row(r):
    print(f"  {r['label']:<35s} "
          f"{r['n_supply']:>4d}×{r['n_demand']:<4d} "
          f"p50={r['p50_ms']:>6.2f}  p95={r['p95_ms']:>6.2f}  "
          f"p99={r['p99_ms']:>7.2f}  max={r['max_ms']:>7.2f}  "
          f"mean={r['mean_ms']:>6.2f} ms")


def main():
    print("=" * 110)
    print(f"  AgriFlow Matching Engine — Latency Benchmark "
          f"({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print("=" * 110)
    print(f"  Target Section 5.5.4: <500ms p99 untuk 38 kab × 19 komoditas")
    print()

    results = []

    # 1. Sample data current
    data = load_all_sample_data()
    results.append(bench_one(
        "Sample data CSV (realistic)",
        data["surplus"], data["deficit"],
        weather=data["weather"], historical=data["historical_prices"],
    ))

    # 2. Synthetic 38 kab × 19 komoditas full
    s_full, d_full = make_synthetic_full_jatim()
    results.append(bench_one(
        "Synthetic full Jatim (38×19)",
        s_full, d_full,
    ))

    # 3. Stress 100x100
    s_100, d_100 = make_synthetic_large(100, 100)
    results.append(bench_one(
        "Stress 100×100 (national scale)",
        s_100, d_100,
        iterations=50,
    ))

    # 4. Stress 200x200
    s_200, d_200 = make_synthetic_large(200, 200)
    results.append(bench_one(
        "Stress 200×200",
        s_200, d_200,
        iterations=30,
    ))

    print(f"  {'Configuration':<35s} {'N (s×d)':>9s}    {'p50':>9s}  "
          f"{'p95':>9s}  {'p99':>11s}  {'max':>11s}  {'mean':>11s}")
    print("  " + "-" * 106)
    for r in results:
        print_row(r)

    print()
    target = 500.0
    p99_max = max(r["p99_ms"] for r in results)
    if p99_max < target:
        print(f"  PASS  semua konfigurasi p99 < {target}ms target "
              f"(highest p99 = {p99_max:.2f}ms, "
              f"margin {(target - p99_max) / target * 100:.1f}%)")
    else:
        print(f"  FAIL  p99 {p99_max:.2f}ms melebihi target {target}ms")
    print()


if __name__ == "__main__":
    main()
