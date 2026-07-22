"""
benchmarks/weight_sensitivity.py — Scoring-weight sensitivity harness.

WHY THIS EXISTS
    The Layer-2 multi-objective score uses five fixed weights
    (distance 0.22, volume 0.22, price 0.22, perishability 0.18, climate 0.16;
    scoring.DEFAULT_WEIGHTS). Those five numbers have no elicitation (no AHP,
    no expert panel) and no published sensitivity analysis, while the LESS
    influential equity thresholds already get `boundary_perturbation` in
    equity_comparison.py. A reviewer can fairly ask: "the weights are arbitrary,
    so do your conclusions move when you perturb them?" This harness answers that
    empirically, mirroring the equity boundary_perturbation idea but on the
    scoring weights.

WHAT IT DOES (isolates ONLY the weight vector, everything else held fixed)
    Baseline = the production allocation with DEFAULT_WEIGHTS on a no-event date.
    1. One-at-a-time (OAT): shift each weight by +/-0.02 and +/-0.05, renormalise
       the five weights back to sum 1, re-run the FULL AgriFlow allocation, and
       measure how far the outcome moves (coverage, Gini, Sampang/Bangkalan
       fulfillment) and how much the allocation itself churns vs baseline.
    2. Global neighborhood: sample weight vectors from a Dirichlet centred on the
       default and report the distribution of coverage and Gini plus the mean
       allocation stability. This shows robustness to the whole simplex
       neighbourhood, not just axis-aligned shifts.

    To make the study independent of the event-weight logic, every run overrides
    ALL weight profiles (DEFAULT / RAMADAN / IMLEK / NATAL / SCHOOL_START /
    IMPORT_POLICY) to the SAME vector, so run_matching uses exactly that vector
    whichever branch fires. The baseline overrides them all to DEFAULT_WEIGHTS,
    so the comparison is apples-to-apples and isolates the five numbers.

ALLOCATION-STABILITY metrics vs baseline
    key_jaccard   = |matched_keys_A & matched_keys_B| / |A | B|  (1.0 = identical set)
    tons_moved_pct= 0.5 * sum |matched_A - matched_B| / total_demand * 100
                    (share of demanded tons whose allocation changed)

INTERPRETATION
    Small coverage/Gini swings + high Jaccard  -> the weights are a tunable policy
    prior whose exact values do not materially change conclusions (defensible).
    Large swings                                -> the arbitrary weights are a real
    vulnerability and must be elicited (AHP) or the claim softened.

Run:
    python benchmarks/weight_sensitivity.py
    python benchmarks/weight_sensitivity.py --samples 500 --conc 300 --seed 7
    python benchmarks/weight_sensitivity.py --json benchmarks/output/weight_sensitivity.json

Author: Hilmi (https://master-hilmi.vercel.app/)
"""
from __future__ import annotations
import argparse
import contextlib
import json
import os
import sys
from typing import Dict, List, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from matching_engine import run_matching
from matching_engine import scoring
from matching_engine.models import LogisticsContext
from sample_data.loader import load_all_sample_data

from benchmarks._metrics import gini, kab_fulfillment, total_deficit_covered
from benchmarks.equity_comparison import (
    BANGKALAN_ID,
    SAMPANG_ID,
    _build_demand_tons,
    _report_to_matched_tons,
)

# Order matters for Dirichlet vectors and printing.
WEIGHT_KEYS: List[str] = ["distance", "volume", "price", "perishability", "climate"]

# All weight-profile dicts the engine may select in run_matching.
_PROFILE_ATTRS = [
    "DEFAULT_WEIGHTS",
    "RAMADAN_WEIGHTS",
    "IMLEK_WEIGHTS",
    "NATAL_WEIGHTS",
    "SCHOOL_START_WEIGHTS",
    "IMPORT_POLICY_WEIGHTS",
]

# A date with no active demand event, so the else-branch (DEFAULT) is the natural
# selection before we override. Overriding all profiles makes the run robust even
# if this ever coincides with an event.
import datetime
_NEUTRAL_DATE = datetime.datetime(2026, 9, 15)


@contextlib.contextmanager
def _override_all_weights(w: Dict[str, float]):
    """Temporarily point every weight profile at `w`; restore on exit."""
    saved = {attr: getattr(scoring, attr) for attr in _PROFILE_ATTRS}
    try:
        for attr in _PROFILE_ATTRS:
            setattr(scoring, attr, dict(w))
        yield
    finally:
        for attr, orig in saved.items():
            setattr(scoring, attr, orig)


def _normalise(w: Dict[str, float]) -> Dict[str, float]:
    s = sum(w[k] for k in WEIGHT_KEYS)
    return {k: w[k] / s for k in WEIGHT_KEYS}


def _run(data, logistics, w: Dict[str, float]) -> Dict[str, object]:
    """Run the full AgriFlow allocation with weight vector `w`; return outcome."""
    with _override_all_weights(w):
        report = run_matching(
            data["surplus"], data["deficit"],
            logistics=logistics,
            weather_forecasts=data["weather"],
            # None on purpose — see equity_comparison_constrained.py. The real PIHPS
            # stats would drop nodes from this synthetic fixture, and a sensitivity
            # sweep must vary only the weights.
            historical_prices=None,
            reference_date=_NEUTRAL_DATE,
        )
    matched = _report_to_matched_tons(report)
    return {
        "matched": matched,
        "weights_used": report.run_metadata.get("weights_used"),
    }


def _outcome_metrics(matched, demand_tons) -> Dict[str, float]:
    return {
        "coverage": total_deficit_covered(matched, demand_tons),
        "gini": gini(matched, demand_tons),
        "sampang": kab_fulfillment(matched, demand_tons, SAMPANG_ID),
        "bangkalan": kab_fulfillment(matched, demand_tons, BANGKALAN_ID),
    }


def _stability(matched_a, matched_b, demand_tons) -> Dict[str, float]:
    """Allocation churn of B relative to A."""
    keys_a = {k for k, v in matched_a.items() if v > 1e-9}
    keys_b = {k for k, v in matched_b.items() if v > 1e-9}
    union = keys_a | keys_b
    inter = keys_a & keys_b
    jaccard = 1.0 if not union else len(inter) / len(union)

    total_demand = sum(demand_tons.values()) or 1.0
    moved = 0.0
    for k in set(matched_a) | set(matched_b):
        moved += abs(matched_a.get(k, 0.0) - matched_b.get(k, 0.0))
    tons_moved_pct = 0.5 * moved / total_demand * 100.0
    return {"key_jaccard": jaccard, "tons_moved_pct": tons_moved_pct}


def main():
    ap = argparse.ArgumentParser(description="Scoring-weight sensitivity harness")
    ap.add_argument("--samples", type=int, default=300,
                    help="Dirichlet neighbourhood samples (default 300)")
    ap.add_argument("--conc", type=float, default=400.0,
                    help="Dirichlet concentration (higher = tighter around default)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--json", type=str, default=None, help="Optional JSON dump path")
    args = ap.parse_args()

    print("=" * 78)
    print("  AGRIFLOW SCORING-WEIGHT SENSITIVITY HARNESS")
    print("=" * 78)
    print("  Loading Jatim sample data ...")
    data = load_all_sample_data()
    logistics = LogisticsContext()
    demand_tons = _build_demand_tons(data["deficit"])

    w0 = _normalise(dict(scoring.DEFAULT_WEIGHTS))
    print("  Default weights:",
          ", ".join(f"{k}={w0[k]:.3f}" for k in WEIGHT_KEYS))
    print()

    # ---- Baseline (default weights) ----
    base = _run(data, logistics, w0)
    base_matched = base["matched"]
    base_metrics = _outcome_metrics(base_matched, demand_tons)
    # Sanity: the override must actually have taken effect.
    assert base["weights_used"] is not None
    print(f"  BASELINE  coverage={base_metrics['coverage']:.4f}  "
          f"gini={base_metrics['gini']:.4f}  "
          f"sampang={base_metrics['sampang']:.4f}  "
          f"bangkalan={base_metrics['bangkalan']:.4f}")
    print()

    # ---- 1. One-at-a-time perturbation ----
    print("=" * 78)
    print("  TABLE 1 — ONE-AT-A-TIME WEIGHT PERTURBATION")
    print("  Each row: shift one weight by delta, renormalise, re-run.")
    print("  d(coverage)/d(gini) = change vs baseline; Jaccard/tons-moved = churn.")
    print("=" * 78)
    header = ("| weight        | delta | coverage | dCover  | gini   | dGini   "
              "| Jaccard | tons_moved% |")
    sep = ("|---------------|-------|----------|---------|--------|---------"
           "|---------|-------------|")
    print(header)
    print(sep)

    oat_rows = []
    for key in WEIGHT_KEYS:
        for delta in (-0.05, -0.02, 0.02, 0.05):
            w = dict(w0)
            w[key] = max(0.0, w[key] + delta)
            w = _normalise(w)
            r = _run(data, logistics, w)
            m = _outcome_metrics(r["matched"], demand_tons)
            st = _stability(base_matched, r["matched"], demand_tons)
            row = {
                "weight": key, "delta": delta,
                "coverage": m["coverage"], "dcover": m["coverage"] - base_metrics["coverage"],
                "gini": m["gini"], "dgini": m["gini"] - base_metrics["gini"],
                "key_jaccard": st["key_jaccard"], "tons_moved_pct": st["tons_moved_pct"],
            }
            oat_rows.append(row)
            print(f"| {key:<13s} | {delta:+.2f} | {m['coverage']:.4f}   "
                  f"| {row['dcover']:+.4f} | {m['gini']:.4f} | {row['dgini']:+.4f} "
                  f"| {st['key_jaccard']:.4f}  | {st['tons_moved_pct']:8.2f}    |")
    print()

    # ---- 2. Global Dirichlet neighbourhood ----
    rng = np.random.default_rng(args.seed)
    alpha = np.array([max(w0[k], 1e-6) * args.conc for k in WEIGHT_KEYS])
    cov_s, gini_s, jac_s, moved_s, l1_s = [], [], [], [], []
    for _ in range(args.samples):
        vec = rng.dirichlet(alpha)
        w = {k: float(vec[i]) for i, k in enumerate(WEIGHT_KEYS)}
        r = _run(data, logistics, w)
        m = _outcome_metrics(r["matched"], demand_tons)
        st = _stability(base_matched, r["matched"], demand_tons)
        cov_s.append(m["coverage"]); gini_s.append(m["gini"])
        jac_s.append(st["key_jaccard"]); moved_s.append(st["tons_moved_pct"])
        l1_s.append(sum(abs(w[k] - w0[k]) for k in WEIGHT_KEYS))

    def _stat(a):
        a = np.array(a)
        return float(a.mean()), float(a.std()), float(a.min()), float(a.max())

    cov_m, cov_sd, cov_lo, cov_hi = _stat(cov_s)
    gin_m, gin_sd, gin_lo, gin_hi = _stat(gini_s)
    jac_m, _, jac_lo, _ = _stat(jac_s)
    mov_m, _, _, mov_hi = _stat(moved_s)
    l1_m = float(np.mean(l1_s))

    print("=" * 78)
    print(f"  TABLE 2 — GLOBAL NEIGHBOURHOOD  (N={args.samples}, "
          f"Dirichlet conc={args.conc:g}, mean L1 dist from default={l1_m:.3f})")
    print("=" * 78)
    print(f"  coverage : mean {cov_m:.4f}  sd {cov_sd:.4f}  "
          f"range [{cov_lo:.4f}, {cov_hi:.4f}]")
    print(f"  gini     : mean {gin_m:.4f}  sd {gin_sd:.4f}  "
          f"range [{gin_lo:.4f}, {gin_hi:.4f}]")
    print(f"  Jaccard  : mean {jac_m:.4f}  min {jac_lo:.4f}   "
          f"(1.0 = allocation identical to default)")
    print(f"  tons moved: mean {mov_m:.2f}%  max {mov_hi:.2f}%")
    print()

    # ---- Verdict ----
    max_dcov = max(abs(r["dcover"]) for r in oat_rows)
    max_dgini = max(abs(r["dgini"]) for r in oat_rows)
    min_jac = min([r["key_jaccard"] for r in oat_rows] + [jac_lo])
    max_moved = max([r["tons_moved_pct"] for r in oat_rows] + [mov_hi])

    print("=" * 78)
    print("  VERDICT")
    print("=" * 78)
    print(f"  Max |d coverage| across all perturbations : {max_dcov:.4f}")
    print(f"  Max |d gini|     across all perturbations : {max_dgini:.4f}")
    print(f"  Min allocation Jaccard vs default         : {min_jac:.4f}")
    print(f"  Max tons reallocated                      : {max_moved:.2f}%")
    stable = (max_dcov < 0.02 and max_dgini < 0.02 and min_jac > 0.90)
    if stable:
        print("  => STABLE: outcome barely moves in a +/-0.05 weight neighbourhood.")
        print("     The five weights act as a tunable policy prior; their exact")
        print("     values do not materially change coverage or equity conclusions.")
    else:
        print("  => SENSITIVE: outcome moves materially with the weights.")
        print("     Elicit the weights (AHP/best-worst) or soften any claim that")
        print("     depends on their specific values.")
    print()

    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        out = {
            "default_weights": w0,
            "baseline": base_metrics,
            "oat": oat_rows,
            "global": {
                "samples": args.samples, "conc": args.conc,
                "mean_l1_dist": l1_m,
                "coverage": {"mean": cov_m, "sd": cov_sd, "min": cov_lo, "max": cov_hi},
                "gini": {"mean": gin_m, "sd": gin_sd, "min": gin_lo, "max": gin_hi},
                "jaccard": {"mean": jac_m, "min": jac_lo},
                "tons_moved_pct": {"mean": mov_m, "max": mov_hi},
            },
            "verdict": {
                "max_abs_dcoverage": max_dcov, "max_abs_dgini": max_dgini,
                "min_jaccard": min_jac, "max_tons_moved_pct": max_moved,
                "stable": bool(stable),
            },
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        print(f"  Wrote JSON -> {args.json}")


if __name__ == "__main__":
    main()
