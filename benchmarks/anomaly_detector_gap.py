"""
benchmarks/anomaly_detector_gap.py — Quantifies the gap between AgriFlow's TWO
price-anomaly detectors on the project's own real data.

BACKGROUND
----------
Two detectors exist in the codebase, both in the production path:

  matching_engine/engine.py:62  detect_price_anomaly(node, historical_median,
      historical_std) -- z_score = |price - median| / std, flag if > 3.0
      (PRICE_ANOMALY_SIGMA). This is what actually gates matching: called at
      engine.py:416 and :429 inside run_matching()'s D3 preprocessing, and a
      flagged node is DROPPED from the surplus/deficit pool entirely (not just
      down-weighted).

  analysis/price_anomaly.py    detect_anomalies() -- S-H-ESD: deseasonalise
      (rolling-median trend + monthly seasonal), then robust MAD on the
      residual, with a persistence filter. This is validated against the
      literature (Hochenbaum/Vallis/Kejariwal 2017) and is what feeds the
      dashboard anomaly panel / API -- NOT the matching engine.

detect_price_anomaly's std is non-robust: a real outlier inflates std, which
shrinks the z-score of ALL points (including the outlier itself and future
genuine anomalies) -- the classic "masking effect" in robust statistics. This
script measures whether that mechanism is real on THIS project's actual price
data, and quantifies it two ways:

  PART 1 -- "As shipped" gap on real data.
      The production historical_prices dict is NOT a rolling window -- it is a
      single STATIC (median, std) constant per commodity, hand-set in
      sample_data/historical_price_stats.csv (mirrored into db/schema.sql's
      historical_prices table). This part runs the ACTUAL shipped function,
      detect_price_anomaly(), against every real observed price in
      sample_data/price_history/*.csv using the ACTUAL shipped static
      constants, and compares the flag set against the already-validated
      S-H-ESD persistent-anomaly set (ground truth for "this was a real
      event"). Reports recall (of genuine persistent anomalies, how many does
      the static 3-sigma catch) and precision-adjacent flag volume.

  PART 2 -- Masking mechanism, isolated, on real price levels.
      Simulates the scenario the code's OWN docstrings claim ("historical_prices:
      dict commodity_code -> (median, std) 30-day rolling", engine.py:352,370)
      but the shipped loaders never actually implement: a rolling 30-day window
      recomputed from real data. Calls the ACTUAL detect_price_anomaly()
      function (not a re-implementation) with median/std computed from a
      window seeded with real cabai_rawit/beras_medium price levels, sweeping
      the number of contaminating outliers already present in that window
      (0..~40% of the window), and reports at what contamination fraction the
      REAL genuine spike stops being flagged. Cross-checked against the
      MAD-based rule (median +/- k*1.4826*MAD, same k=3.0) at every
      contamination level.

Both parts are seeded (--seed, default 2026) for reproducibility.

Usage:
    python benchmarks/anomaly_detector_gap.py
"""

from __future__ import annotations

import argparse
import os
import random
import statistics
import sys
from datetime import datetime
from typing import Dict, List, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from matching_engine.engine import PRICE_ANOMALY_SIGMA, detect_price_anomaly
from matching_engine.models import Commodity, DemandNode, Kabupaten, Tier
from analysis.price_anomaly import CITY_NAMES, load_series, scan_all

DEFAULT_SEED = 2026
PRICE_HISTORY_DIR = os.path.join(ROOT, "sample_data", "price_history")
HISTORICAL_STATS_CSV = os.path.join(ROOT, "sample_data", "historical_price_stats.csv")


def load_static_stats() -> Dict[str, Tuple[float, float, str]]:
    """Read the ACTUAL shipped static (median, std, source) per commodity."""
    out = {}
    with open(HISTORICAL_STATS_CSV, encoding="utf-8") as fh:
        import csv
        for row in csv.DictReader(fh):
            out[row["commodity_code"]] = (
                float(row["median_idr_per_kg"]),
                float(row["std_idr_per_kg"]),
                row["source"],
            )
    return out


def _dummy_node(price: float):
    """
    Minimal SupplyNode-like stand-in: detect_price_anomaly only reads
    node.price_per_kg, so a lightweight namespace avoids constructing full
    Kabupaten/Commodity graphs for a million-point scan.
    """
    class _N:
        pass
    n = _N()
    n.price_per_kg = price
    return n


# =============================================================================
# PART 1 — "AS SHIPPED": static constants vs real observed prices
# =============================================================================

def run_as_shipped_gap(seed: int) -> None:
    print("=" * 82)
    print("  PART 1 — 'As shipped': static (median, std) vs real PIHPS Jatim prices")
    print("=" * 82)
    print(f"  historical_price_stats.csv is a STATIC constant per commodity "
          f"(not a rolling window,\n  despite engine.py's docstring claiming "
          f"'30-day rolling') -- this reproduces exactly what\n  production does "
          f"today: detect_price_anomaly() called with the SAME fixed (median, std)\n"
          f"  against every real observed price.\n")

    static_stats = load_static_stats()
    ground_truth = scan_all(PRICE_HISTORY_DIR, window=30, k=3.0, persist=2)
    ground_truth_persistent = [a for a in ground_truth if a["persistent"]]

    header = (f"  {'commodity':<15}{'source':<38}{'n_obs':>8}{'static_3σ_flags':>17}"
              f"{'MAD_persistent':>16}{'overlap':>9}{'recall':>9}")
    print(header)
    print("  " + "-" * (len(header) - 2))

    total_obs = 0
    total_static_flags = 0
    total_mad_persistent = 0
    total_overlap = 0

    for commodity, (median, std, source) in sorted(static_stats.items()):
        gt_comm = [a for a in ground_truth_persistent if a["commodity_code"] == commodity]
        if not gt_comm and not any(True for _ in []):
            pass  # commodity may still have price series even with 0 persistent anomalies

        n_obs = 0
        static_flag_dates = set()  # (city_id, date)
        for city_id in CITY_NAMES:
            series = load_series(commodity, city_id, PRICE_HISTORY_DIR)
            if not series:
                continue
            for date, price in series:
                n_obs += 1
                if detect_price_anomaly(_dummy_node(price), median, std):
                    static_flag_dates.add((city_id, date))

        if n_obs == 0:
            continue  # commodity has no real price series (e.g. cabai_merah, tomat, ...)

        gt_dates = {(a["city_id"], a["date"]) for a in gt_comm}
        overlap = static_flag_dates & gt_dates
        recall = (len(overlap) / len(gt_dates) * 100.0) if gt_dates else float("nan")

        total_obs += n_obs
        total_static_flags += len(static_flag_dates)
        total_mad_persistent += len(gt_dates)
        total_overlap += len(overlap)

        recall_str = f"{recall:5.1f}%" if gt_dates else "n/a"
        print(f"  {commodity:<15}{source:<38}{n_obs:>8}{len(static_flag_dates):>17}"
              f"{len(gt_dates):>16}{len(overlap):>9}{recall_str:>9}")

    print()
    overall_recall = (total_overlap / total_mad_persistent * 100.0) if total_mad_persistent else 0.0
    print(f"  TOTAL: {total_obs} real observations across 7 commodities x 8 IHK cities.")
    print(f"  Static 3σ flagged {total_static_flags} points total.")
    print(f"  S-H-ESD (robust, validated) flagged {total_mad_persistent} PERSISTENT genuine events.")
    print(f"  Static 3σ caught {total_overlap}/{total_mad_persistent} of those "
          f"({overall_recall:.1f}% recall) on the SAME date+city.")
    print(f"\n  Caveat: telur_ayam and daging_ayam static constants are labelled "
          f"'SYNTHETIC' in\n  historical_price_stats.csv (never calibrated against "
          f"the real PIHPS series at all) --\n  their recall numbers reflect a "
          f"made-up threshold, not a stale-but-real one.\n")


# =============================================================================
# PART 2 — Masking mechanism, isolated, on real price levels
# =============================================================================

def run_masking_mechanism(seed: int, window: int = 30, trials: int = 200) -> None:
    print("=" * 82)
    print("  PART 2 — Masking mechanism (rolling window, real price levels)")
    print("=" * 82)
    print(f"  Simulates the 'rolling {window}-day' design the docstring promises "
          f"(engine.py:352)\n  but the shipped loader never implements. Calls the "
          f"ACTUAL detect_price_anomaly()\n  function with median/std computed "
          f"from a window built on REAL median price levels\n  (not an arbitrary "
          f"Rp30,000 placeholder), sweeping how many contaminating outliers\n"
          f"  are already sitting in that window when a genuine 3x spike arrives.\n")

    # Real median price levels, PIHPS Jatim (Surabaya, 3578), for grounding.
    scenarios = [
        ("cabai_rawit (volatile, MAPE 23.2% per forecasting validation)", 41_000.0),
        ("beras_medium (low-volatility staple)", 14_000.0),
    ]

    for label, base_price in scenarios:
        print(f"  --- {label}: base price Rp{base_price:,.0f}/kg ---")
        header = (f"  {'contam_n':>9}{'contam_%':>10}{'mean_std':>12}"
                  f"{'3σ_flags_spike':>16}{'MAD_flags_spike':>17}")
        print(header)

        for contam_n in range(0, int(window * 0.5) + 1, 2):
            contam_frac = contam_n / window * 100.0
            rng = random.Random(seed + contam_n)
            spike3sigma_hits = 0
            mad_hits = 0
            stds = []

            for _ in range(trials):
                # Build a window of `window` observations: base price with mild
                # noise, `contam_n` of them replaced by contaminating spikes
                # (2-3x base, random sign/magnitude), and ONE genuine test spike
                # (3x base) at a fixed slot -- this is the point we ask both
                # detectors to catch.
                win = [base_price * rng.gauss(1.0, 0.03) for _ in range(window)]
                contam_positions = rng.sample(range(window - 1), k=min(contam_n, window - 1))
                for p in contam_positions:
                    mult = rng.uniform(2.0, 3.0) * rng.choice([1, -0.4])
                    win[p] = max(1.0, base_price * abs(mult))
                test_spike_price = base_price * 3.0
                win[-1] = test_spike_price  # genuine anomaly under test

                median = statistics.median(win)
                std = statistics.pstdev(win)
                stds.append(std)

                # ACTUAL shipped function — not a re-implementation.
                if detect_price_anomaly(_dummy_node(test_spike_price), median, std):
                    spike3sigma_hits += 1

                # MAD-equivalent at the SAME k, matching analysis/price_anomaly's
                # spread estimator (robust) instead of engine.py's std (non-robust).
                abs_devs = [abs(x - median) for x in win]
                mad = statistics.median(abs_devs)
                if mad > 0:
                    mad_z = abs(test_spike_price - median) / (1.4826 * mad)
                    if mad_z > PRICE_ANOMALY_SIGMA:
                        mad_hits += 1
                else:
                    mad_hits += 1  # flat window + spike -> trivially anomalous

            mean_std = statistics.mean(stds)
            print(f"  {contam_n:>9}{contam_frac:>9.1f}%{mean_std:>12,.0f}"
                  f"{spike3sigma_hits:>10}/{trials:<5}{mad_hits:>10}/{trials:<5}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Quantify the gap between engine.py's z-score detector and "
                     "analysis/price_anomaly's MAD detector, on AgriFlow's own real data.",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--trials", type=int, default=200)
    args = parser.parse_args()

    print(f"AgriFlow — Anomaly Detector Gap Analysis  (seed={args.seed})")
    print(f"Run: {datetime.now().isoformat(timespec='seconds')}\n")

    run_as_shipped_gap(args.seed)
    run_masking_mechanism(args.seed, trials=args.trials)


if __name__ == "__main__":
    main()
