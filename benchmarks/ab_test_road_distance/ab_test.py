"""
A/B test: straight-line (haversine) versus OSRM road distance in the matching
engine, measured on the sample dataset.

ARM A (control)   : haversine only. `constraints.road_distance_km` is stubbed to
                    return None, so `distance_between` falls back to the
                    great-circle formula for every pair.
ARM B (treatment) : road distance. The engine's production default, which reads
                    the precomputed OSRM matrix in
                    sample_data/road_distance_jatim.csv.

HISTORY, so the numbers are read correctly:
    This experiment is what decided the question in May 2026, back when haversine
    was the production default. Arm B won, so road distance was adopted and
    `distance_between` now prefers it. Re-running the ORIGINAL script today
    reports a flat zero delta, but that is an artifact: it patched
    `haversine_km`, which the road-distance path no longer calls. The arms below
    were re-pointed at `road_distance_km` so the comparison again measures the
    thing it claims to measure. Arm B is the shipped behaviour; Arm A is the
    counterfactual we moved away from.

Run:
    python benchmarks/ab_test_road_distance/ab_test.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

OSRM_CSV = Path(__file__).parent / "osrm_distance_matrix.csv"
KAB_CSV = ROOT / "sample_data" / "kabupaten_jatim.csv"


def build_road_lookup():
    """Read the raw OSRM pull, purely to report how many pairs back the test."""
    coord_to_id = {}
    with open(KAB_CSV, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            key = (round(float(row["latitude"]), 4), round(float(row["longitude"]), 4))
            coord_to_id[key] = row["kab_id"]

    road = {}
    with open(OSRM_CSV, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            road[(row["from_id"], row["to_id"])] = float(row["road_km"])
    return coord_to_id, road


def run_engine(label, disable_road):
    """Reload engine modules so the arm's patch takes effect."""
    # Remove cached modules to force re-import with the patch in place
    for mod in list(sys.modules):
        if mod.startswith("matching_engine") or mod.startswith("sample_data"):
            del sys.modules[mod]

    import matching_engine.constraints as constraints
    if disable_road:
        # distance_between() asks road_distance_km() first and falls back to
        # haversine when it returns None. Stubbing it out yields a pure
        # great-circle arm without touching any other engine behaviour.
        constraints.road_distance_km = lambda kab_a_id, kab_b_id: None

    from matching_engine import run_matching, LogisticsContext
    from sample_data import load_all_sample_data

    data = load_all_sample_data()
    report = run_matching(
        surplus_nodes=data["surplus"],
        deficit_nodes=data["deficit"],
        logistics=LogisticsContext(),
        weather_forecasts=data.get("weather"),
        historical_prices=data.get("historical_prices"),
    )
    print(f"\n[{label}] matches={len(report.matches)}  "
          f"unmatched_supply={len(report.unmatched_surplus)}  "
          f"unmatched_demand={len(report.unmatched_deficit)}  "
          f"warnings={len(report.warnings)}")
    return report


def diff(baseline, treatment):
    print("\n" + "=" * 90)
    print("DIFF  Arm A (haversine only) vs Arm B (road distance)")
    print("=" * 90)

    b_matches = baseline.matches
    t_matches = treatment.matches

    def key(m):
        return (m.surplus.kabupaten.id, m.deficit.kabupaten.id,
                m.surplus.commodity.code)

    b_keys = {key(m) for m in b_matches}
    t_keys = {key(m) for m in t_matches}

    only_b = b_keys - t_keys
    only_t = t_keys - b_keys
    common = b_keys & t_keys

    print(f"\nMatch set delta:")
    print(f"  arm A only (lost when switching to road):       {len(only_b)}")
    print(f"  arm B only (new matches via road):               {len(only_t)}")
    print(f"  common (same surplus->deficit->commodity pair):  {len(common)}")

    # Total welfare
    b_score = sum(m.final_score * m.matched_volume_tons for m in b_matches)
    t_score = sum(m.final_score * m.matched_volume_tons for m in t_matches)
    print(f"\nTotal volume-weighted final_score:")
    print(f"  baseline:   {b_score:10.1f}")
    print(f"  treatment:  {t_score:10.1f}")
    print(f"  delta:      {t_score - b_score:+10.1f}  ({100*(t_score-b_score)/b_score:+.2f}%)")

    # Total matched volume
    b_vol = sum(m.matched_volume_tons for m in b_matches)
    t_vol = sum(m.matched_volume_tons for m in t_matches)
    print(f"\nTotal matched volume (tons):")
    print(f"  baseline:   {b_vol:10.1f}")
    print(f"  treatment:  {t_vol:10.1f}")
    print(f"  delta:      {t_vol - b_vol:+10.1f}  ({100*(t_vol-b_vol)/b_vol:+.2f}%)")

    # Show top-10 baseline matches and whether they survive
    print(f"\nTop-10 arm A matches - did they survive in arm B?")
    b_by_key = {key(m): m for m in b_matches}
    t_by_key = {key(m): m for m in t_matches}
    top10 = sorted(b_matches, key=lambda m: m.final_score, reverse=True)[:10]
    for i, m in enumerate(top10, 1):
        k = key(m)
        if k in t_by_key:
            tm = t_by_key[k]
            d_score = tm.final_score - m.final_score
            d_dist = tm.distance_km - m.distance_km
            mark = "KEPT"
            print(f"  {i:>2}. {mark}   {m.surplus.kabupaten.nama:<18s}->{m.deficit.kabupaten.nama:<18s}  "
                  f"{m.surplus.commodity.code:<14s}  "
                  f"dist {m.distance_km:5.0f}->{tm.distance_km:5.0f}km ({d_dist:+5.0f})  "
                  f"score {m.final_score:5.1f}->{tm.final_score:5.1f} ({d_score:+5.1f})")
        else:
            print(f"  {i:>2}. LOST   {m.surplus.kabupaten.nama:<18s}->{m.deficit.kabupaten.nama:<18s}  "
                  f"{m.surplus.commodity.code:<14s}  "
                  f"dist {m.distance_km:5.0f}km  score {m.final_score:5.1f}  -- DROPPED in treatment")

    # New matches in treatment
    new = [m for m in t_matches if key(m) not in b_by_key]
    if new:
        print(f"\nNew matches in treatment (not in baseline) — top 5 by score:")
        for m in sorted(new, key=lambda m: m.final_score, reverse=True)[:5]:
            print(f"     NEW  {m.surplus.kabupaten.nama:<18s}->{m.deficit.kabupaten.nama:<18s}  "
                  f"{m.surplus.commodity.code:<14s}  "
                  f"dist {m.distance_km:5.0f}km  score {m.final_score:5.1f}")

    # Lost matches detail
    lost = [m for m in b_matches if key(m) not in t_by_key]
    if lost:
        print(f"\nLost matches in treatment (not preserved) — top 5 by score:")
        for m in sorted(lost, key=lambda m: m.final_score, reverse=True)[:5]:
            print(f"     LOST {m.surplus.kabupaten.nama:<18s}->{m.deficit.kabupaten.nama:<18s}  "
                  f"{m.surplus.commodity.code:<14s}  "
                  f"haversine dist {m.distance_km:5.0f}km  score {m.final_score:5.1f}")


def main():
    coord_to_id, road = build_road_lookup()
    print(f"[setup] {len(road)} pairwise road distances in the OSRM pull")
    print(f"[setup] {len(coord_to_id)} kabupaten coordinates indexed")

    baseline = run_engine("ARM A  haversine only", disable_road=True)
    treatment = run_engine("ARM B  road distance (production default)",
                           disable_road=False)

    diff(baseline, treatment)


if __name__ == "__main__":
    main()
