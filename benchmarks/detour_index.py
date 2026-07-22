"""
benchmarks/detour_index.py — how far the road actually is, versus the straight line.

WHY THIS EXISTS
---------------
`distance_between()` prefers the precomputed OSRM road matrix and falls back to
haversine when a pair is missing. That fallback is not neutral: a great-circle
distance is always shorter than the road, so every constraint keyed on distance
(the perishability radius above all) becomes systematically looser than it should
be. The A/B test in benchmarks/ab_test_road_distance/ shows the consequence at the
allocation level. This script measures the cause, so the size of the bias is a
number rather than an intuition.

The detour index of a pair is road_km / haversine_km. It is >= 1 by construction;
1.0 would mean a perfectly straight road.

Run:
    python benchmarks/detour_index.py
    python benchmarks/detour_index.py --json benchmarks/output/detour_index.json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

KAB_CSV = ROOT / "sample_data" / "kabupaten_jatim.csv"
OSRM_CSV = ROOT / "benchmarks" / "ab_test_road_distance" / "osrm_distance_matrix.csv"

# Below this, a ratio is dominated by centroid placement error rather than by the
# road network, so the pair says nothing useful about detour.
MIN_HAVERSINE_KM = 1.0


def _haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    radius = 6371.0
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return radius * 2 * math.asin(math.sqrt(h))


def load_pairs():
    coords = {}
    with open(KAB_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            coords[row["kab_id"]] = (
                float(row["latitude"]), float(row["longitude"]), row["nama"],
            )

    pairs = []
    with open(OSRM_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            src, dst = row["from_id"], row["to_id"]
            if src == dst or src not in coords or dst not in coords:
                continue
            straight = _haversine_km(coords[src][:2], coords[dst][:2])
            if straight < MIN_HAVERSINE_KM:
                continue
            road = float(row["road_km"])
            pairs.append({
                "from": coords[src][2], "to": coords[dst][2],
                "haversine_km": round(straight, 2), "road_km": round(road, 2),
                "detour": round(road / straight, 4),
            })
    return pairs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    ap.add_argument("--top", type=int, default=5)
    args = ap.parse_args()

    pairs = load_pairs()
    if not pairs:
        print("No usable pairs found.")
        return 1

    ratios = sorted(p["detour"] for p in pairs)
    n = len(ratios)
    stats = {
        "pairs": n,
        "median": round(statistics.median(ratios), 4),
        "mean": round(statistics.mean(ratios), 4),
        "p10": round(ratios[n // 10], 4),
        "p90": round(ratios[9 * n // 10], 4),
        "max": round(ratios[-1], 4),
        "share_above_1_5": round(100 * sum(1 for r in ratios if r > 1.5) / n, 2),
    }

    print("Detour index (road km / straight-line km), East Java kabupaten pairs")
    print("=" * 70)
    print(f"  pairs evaluated : {stats['pairs']}")
    print(f"  median          : {stats['median']:.3f}")
    print(f"  mean            : {stats['mean']:.3f}")
    print(f"  p10 / p90       : {stats['p10']:.3f} / {stats['p90']:.3f}")
    print(f"  max             : {stats['max']:.3f}")
    print(f"  share > 1.5     : {stats['share_above_1_5']:.1f}%")

    worst = sorted(pairs, key=lambda p: p["detour"], reverse=True)[: args.top]
    print(f"\n  {args.top} worst detours:")
    for p in worst:
        print(f"    {p['from']:<18s} -> {p['to']:<18s} "
              f"{p['haversine_km']:6.1f} km straight, {p['road_km']:6.1f} km by road "
              f"(x{p['detour']:.2f})")

    # State the base explicitly: the same ratio yields two different percentages,
    # and naming one without its comparator is how this gets misquoted.
    longer = 100 * (stats["median"] - 1)
    shorter = 100 * (1 - 1 / stats["median"])
    print(f"\n  Reading: at the median pair the road is {longer:.1f}% longer than the "
          f"straight line, i.e. the straight line is {shorter:.1f}% shorter than the "
          "real travel distance. Madura-to-mainland pairs are far worse, since they "
          "must route via the Suramadu bridge.")

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"stats": stats, "worst": worst, "pairs": pairs},
                                  indent=2), encoding="utf-8")
        print(f"\n  Wrote JSON -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
