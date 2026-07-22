"""
Compare OSRM road distance vs haversine for 38 Jatim kabupaten.
Reports distribution of ratio road_km / haversine_km.

DRA hypothesis: 1.15-1.35x for Pulau Jawa.
"""
from __future__ import annotations

import csv
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from matching_engine.constraints import haversine_km

KAB_CSV = ROOT / "sample_data" / "kabupaten_jatim.csv"
OSRM_CSV = Path(__file__).parent / "osrm_distance_matrix.csv"


def load_coords():
    out = {}
    with open(KAB_CSV, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            out[row["kab_id"]] = (float(row["latitude"]), float(row["longitude"]),
                                  row["nama"])
    return out


def main():
    coords = load_coords()
    print(f"[analyze] {len(coords)} kabupaten loaded")

    ratios = []
    haver_km_list = []
    road_km_list = []
    pairs = []  # (ratio, hav, road, name_from, name_to)

    with open(OSRM_CSV, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            i, j = row["from_id"], row["to_id"]
            if i == j:
                continue  # self-loop, skip
            hav = haversine_km(coords[i][0], coords[i][1],
                               coords[j][0], coords[j][1])
            road = float(row["road_km"])
            if hav < 1.0:
                continue  # avoid div-by-zero & noise
            ratio = road / hav
            ratios.append(ratio)
            haver_km_list.append(hav)
            road_km_list.append(road)
            pairs.append((ratio, hav, road, coords[i][2], coords[j][2]))

    ratios.sort()
    n = len(ratios)
    print(f"\n[analyze] {n} non-self pairs analyzed")
    print(f"  haversine: min={min(haver_km_list):6.1f}  median={statistics.median(haver_km_list):6.1f}  max={max(haver_km_list):6.1f}  km")
    print(f"  road    : min={min(road_km_list):6.1f}  median={statistics.median(road_km_list):6.1f}  max={max(road_km_list):6.1f}  km")
    print(f"\n  road/haversine ratio:")
    print(f"     min     = {ratios[0]:.3f}")
    print(f"     p05     = {ratios[int(0.05*n)]:.3f}")
    print(f"     p25     = {ratios[int(0.25*n)]:.3f}")
    print(f"     median  = {ratios[n//2]:.3f}")
    print(f"     mean    = {statistics.mean(ratios):.3f}")
    print(f"     p75     = {ratios[int(0.75*n)]:.3f}")
    print(f"     p95     = {ratios[int(0.95*n)]:.3f}")
    print(f"     p99     = {ratios[int(0.99*n)]:.3f}")
    print(f"     max     = {ratios[-1]:.3f}")

    # Top-10 worst ratios (most "stretched" routes — terrain/water barriers)
    pairs.sort(reverse=True)
    print(f"\n  Top-10 worst ratios (route detour vs straight line):")
    for ratio, hav, road, fn, tn in pairs[:10]:
        print(f"    {ratio:.2f}x  haversine {hav:6.1f}km -> road {road:6.1f}km   {fn} -> {tn}")

    # How many pairs would change MAX_DISTANCE viability?
    # Cabai 200km, Bawang 300km, Beras 800km, Jagung 500km
    for threshold, label in [(200, "cabai/bawang short"), (500, "jagung mid"), (800, "beras long")]:
        haver_pass = sum(1 for r, h, rd, _, _ in pairs if h <= threshold)
        road_pass = sum(1 for r, h, rd, _, _ in pairs if rd <= threshold)
        delta = haver_pass - road_pass
        print(f"\n  MAX_DISTANCE = {threshold}km ({label}):")
        print(f"    haversine passes: {haver_pass:4d} / {n} pairs")
        print(f"    road     passes: {road_pass:4d} / {n} pairs")
        print(f"    pairs newly REJECTED if we switch to road: {delta}  ({100*delta/n:.1f}%)")


if __name__ == "__main__":
    main()
