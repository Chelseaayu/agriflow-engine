"""
benchmarks/lp_allocator.py -- v1.1 allocator: LP optimum vs shipped greedy,
through the real engine entrypoint (run_matching), on the datasets the API
actually serves.

Why a separate script from greedy_vs_optimal.py: that one measures the gap
against an external LP. This one measures what the engine now returns with
force_strategy="lp", so the number in /api/v1/meta ("welfare_gain_pct") has a
committed, reproducible origin.

Usage:
    python benchmarks/lp_allocator.py
    python benchmarks/lp_allocator.py --json benchmarks/output/lp_allocator.json
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from matching_engine import run_matching  # noqa: E402
from sample_data.loader import load_all_sample_data, load_real_data  # noqa: E402


def _lowest_ipm_fulfillment(report, deficit, ipm_lt: float = 68.0):
    low = [d for d in deficit if d.kabupaten.ipm < ipm_lt]
    need = sum(d.volume_tons for d in low)
    got = sum(m.matched_volume_tons for m in report.matches if m.deficit.kabupaten.ipm < ipm_lt)
    return round(got / need * 100, 1) if need else None


def evaluate(label: str, data: dict, repeats: int = 15) -> dict:
    out = {"label": label, "n_surplus": len(data["surplus"]), "n_deficit": len(data["deficit"])}
    for strat in ("greedy", "lp"):
        lat = []
        rep = None
        for _ in range(repeats):
            t = time.perf_counter()
            rep = run_matching(
                data["surplus"], data["deficit"], force_strategy=strat,
                weather_forecasts=data["weather"], anomaly_keys=set(),
            )
            lat.append((time.perf_counter() - t) * 1000)
        lat.sort()
        deficit_t = sum(d.volume_tons for d in data["deficit"])
        out[strat] = {
            "matches": len(rep.matches),
            "matched_tons": round(rep.run_metadata["matched_tons"], 1),
            "coverage_pct": round(rep.run_metadata["matched_tons"] / deficit_t * 100, 2) if deficit_t else None,
            "welfare": rep.run_metadata["welfare"],
            "low_ipm_fulfillment_pct": _lowest_ipm_fulfillment(rep, data["deficit"]),
            "latency_p50_ms": round(statistics.median(lat), 2),
            "latency_p99_ms": round(lat[-1], 2),
        }
    g, l = out["greedy"]["welfare"], out["lp"]["welfare"]
    out["welfare_gain_pct"] = round((l - g) / g * 100, 2) if g else None
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    results = [
        evaluate("real BPS 2022, 6 komoditas (served)", load_real_data()),
        evaluate("synthetic 19-komoditas fixture (tests only)", load_all_sample_data()),
        evaluate("supply-constrained fixture (La Nina)",
                 load_all_sample_data(surplus_deficit_csv="surplus_deficit_constrained.csv")),
    ]
    print(f"{'dataset':<48}{'strategy':<8}{'matches':>8}{'cov%':>8}{'lowIPM%':>9}{'welfare':>14}{'p50ms':>8}{'p99ms':>8}")
    for r in results:
        for strat in ("greedy", "lp"):
            s = r[strat]
            print(f"{r['label']:<48}{strat:<8}{s['matches']:>8}{s['coverage_pct']:>8}{str(s['low_ipm_fulfillment_pct']):>9}"
                  f"{s['welfare']:>14,.0f}{s['latency_p50_ms']:>8}{s['latency_p99_ms']:>8}")
        print(f"{'':<48}gain    welfare +{r['welfare_gain_pct']}%\n")

    if args.json:
        os.makedirs(os.path.dirname(args.json) or ".", exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       "results": results}, fh, indent=2)
        print(f"wrote {args.json}")


if __name__ == "__main__":
    main()
