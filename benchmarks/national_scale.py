"""
National-scale stress test untuk AgriFlow Matching Engine.

Indonesia: 514 kab/kota × 19 komoditas. Asumsi 50% surplus & 50% deficit
per komoditas → ~4880 supply nodes, ~4880 demand nodes total.

Ini test apakah engine v10 SIAP scale ke nasional, atau masih butuh
optimization untuk handle volume itu.
"""
from __future__ import annotations
import os
import random
import statistics
import sys
import time
from datetime import datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from matching_engine import (
    Commodity, DemandNode, Kabupaten, LogisticsContext, SupplyNode, Tier,
    run_matching,
)
from sample_data.generate_sample_data import KOMODITAS_DATA


def percentile(data, p):
    s = sorted(data)
    k = (len(s) - 1) * p
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


# Indonesia bounding box (kira-kira)
# Sabang: -5.9, 95.3 | Merauke: -8.5, 140.4
# Latitude: -11 to 6
# Longitude: 95 to 141

random.seed(42)


def make_synthetic_indonesia(n_kab: int):
    """Generate synthetic kabupaten dengan koordinat random di seluruh Indonesia."""
    kabs = []
    # Distribusi IPM Indonesia: range ~50-85, mean ~71
    # Berdasarkan BPS 2024: Papua-NTT-Maluku tier rendah (50-65),
    # Jawa-Bali tier menengah-tinggi (70-85), Sumatra mixed
    for i in range(n_kab):
        # IPM distribution skewed towards 65-78 (most kabs)
        ipm = random.gauss(71, 8)
        ipm = max(50, min(86, ipm))
        # Random lat/lon dalam wilayah Indonesia
        lat = random.uniform(-11.0, 6.0)
        lon = random.uniform(95.0, 141.0)
        # 18% Tier 1 (90 kota IHK / 514 kab)
        tier = Tier.HIGH if random.random() < 0.18 else Tier.MEDIUM
        kabs.append(Kabupaten(
            id=f"{i:04d}", nama=f"Kab-{i}",
            latitude=lat, longitude=lon, ipm=round(ipm, 2),
            tier=tier, population=random.randint(100_000, 3_000_000),
        ))
    return kabs


def make_workload(kabs, n_commodities: int, surplus_ratio: float = 0.5):
    """Build supply + demand workload dari kabs untuk n komoditas."""
    komos = [
        Commodity(code=c, nama=n, max_distance_km=md, min_viable_tons=mv,
                  max_fresh_age_days=mf)
        for c, n, md, mv, mf, _ in KOMODITAS_DATA[:n_commodities]
    ]
    surplus, demand = [], []
    for komo in komos:
        for kab in kabs:
            if random.random() < surplus_ratio:
                surplus.append(SupplyNode(
                    kabupaten=kab, commodity=komo,
                    volume_tons=max(komo.min_viable_tons * 5,
                                    random.uniform(10, 200)),
                    price_per_kg=random.uniform(20000, 50000),
                    harvest_age_days=random.randint(0, 3),
                ))
            else:
                demand.append(DemandNode(
                    kabupaten=kab, commodity=komo,
                    volume_tons=max(komo.min_viable_tons * 4,
                                    random.uniform(10, 150)),
                    price_per_kg=random.uniform(40000, 80000),
                ))
    return surplus, demand


def bench(label, surplus, demand, iterations: int = 10):
    logistics = LogisticsContext()
    samples = []
    n_matches = 0
    candidate_pairs = 0

    for _ in range(iterations):
        t = time.perf_counter()
        report = run_matching(surplus, demand, logistics=logistics)
        elapsed_ms = (time.perf_counter() - t) * 1000
        samples.append(elapsed_ms)
        n_matches = len(report.matches)
        candidate_pairs = report.run_metadata.get("candidate_pairs_evaluated", 0)

    return {
        "label": label,
        "n_supply": len(surplus),
        "n_demand": len(demand),
        "n_matches": n_matches,
        "candidate_pairs": candidate_pairs,
        "p50_ms": percentile(samples, 0.50),
        "p95_ms": percentile(samples, 0.95),
        "p99_ms": percentile(samples, 0.99),
        "min_ms": min(samples),
        "max_ms": max(samples),
        "mean_ms": statistics.mean(samples),
    }


def print_result(r):
    over_target = " ⚠ OVER 500ms" if r["p99_ms"] > 500 else ""
    print(f"\n{r['label']}")
    print(f"  Workload: {r['n_supply']} supply × {r['n_demand']} demand")
    print(f"  Matches generated: {r['n_matches']}")
    print(f"  Candidate pairs evaluated: {r['candidate_pairs']:,}")
    print(f"  Latency: p50={r['p50_ms']:.1f}ms  p95={r['p95_ms']:.1f}ms  "
          f"p99={r['p99_ms']:.1f}ms  max={r['max_ms']:.1f}ms{over_target}")


def main():
    print("=" * 90)
    print(f"  NATIONAL SCALE STRESS TEST  ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print("=" * 90)
    print("  Target: <500ms p99 (Section 5.5.4)")
    print("  Indonesia reality: 514 kab/kota × 19 komoditas")

    configs = [
        ("Provinsi (38 kab × 19 komoditas) — baseline Jatim", 38, 19),
        ("Multi-provinsi (100 kab × 19)", 100, 19),
        ("Setengah Indonesia (250 kab × 19)", 250, 19),
        ("Full Indonesia (514 kab × 19) — TARGET NASIONAL", 514, 19),
        ("Stress over-scale (1000 kab × 19)", 1000, 19),
    ]

    results = []
    for label, n_kab, n_komo in configs:
        kabs = make_synthetic_indonesia(n_kab)
        surplus, demand = make_workload(kabs, n_komo)
        # Reduced iterations for large workloads
        iters = 20 if n_kab <= 100 else 5 if n_kab <= 514 else 3
        r = bench(label, surplus, demand, iterations=iters)
        results.append(r)
        print_result(r)

    print()
    print("=" * 90)
    print("  CONCLUSION")
    print("=" * 90)
    national = results[3]  # 514 kab
    if national["p99_ms"] < 500:
        print(f"  ✅ National scale 514 kab × 19 komoditas: p99 = "
              f"{national['p99_ms']:.1f}ms — UNDER 500ms target. SIAP NASIONAL.")
    else:
        scale_factor = national["p99_ms"] / 500
        print(f"  ⚠ National scale 514 kab × 19 komoditas: p99 = "
              f"{national['p99_ms']:.1f}ms — OVER 500ms target")
        print(f"     Slowdown vs target: {scale_factor:.1f}x — butuh optimization")
        print(f"     Optimization yang dapat dipertimbangkan:")
        print(f"       1. Spatial indexing (R-tree / geohash) di Layer 1")
        print(f"       2. Pre-computed distance matrix (cached)")
        print(f"       3. Per-province batching (decompose ke 38 sub-problems)")
        print(f"       4. Parallel processing per komoditas (independent)")


if __name__ == "__main__":
    main()
