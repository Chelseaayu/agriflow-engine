"""
analysis/backtest_baseline.py  --  Reproducible holdout backtest of the DEPLOYED
seasonal-naive forecaster (the method actually served by the dashboard when
TimesFM is unavailable).

WHY THIS EXISTS:
    The deployed forecast_all.json is produced by `_seasonal_naive_forecast`
    (analysis/forecast_timesfm.py).  This script measures that exact function's
    accuracy on a real holdout so the proposal can cite a reproducible MAPE for
    what is actually running -- not an unbacked number.

METHOD (honest, leakage-free):
    For every (commodity, city) daily series in sample_data/price_history/:
      1. Hold out the LAST `horizon` calendar days as the test window.
      2. Train = everything strictly before the holdout.
      3. Forecast with the SAME _seasonal_naive_forecast used in production.
      4. Align forecast dates to actual observed test dates and score.

    Metrics per series: MAPE, MAE, RMSE, and 80%-CI coverage (share of actuals
    inside [p10, p90]).  Aggregated per commodity (mean over cities) and overall.

USAGE:
    python analysis/backtest_baseline.py                 # 30-day holdout, all series
    python analysis/backtest_baseline.py --horizon 14
    python analysis/backtest_baseline.py --json analysis/output/backtest_baseline.json

OUTPUT:
    - prints per-commodity + overall table
    - optional JSON dump of full results
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
from collections import defaultdict

import numpy as np
import pandas as pd

from forecast_timesfm import _seasonal_naive_forecast  # the deployed baseline

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRICE_DIR = os.path.join(ROOT, "sample_data", "price_history")

# file -> canonical commodity (mirrors price_ingest mapping)
FILE_COMMODITY = {
    "bawang_merah_cleaned.csv": "bawang_merah",
    "bawang_putih_cleaned.csv": "bawang_putih",
    "cabe_rawit_cleaned.csv": "cabai_rawit",
    "daging_ayam_cleaned.csv": "daging_ayam",
    "telur_ayam_cleaned.csv": "telur_ayam",
    "medium1_cleaned.csv": "beras_medium",
    "medium2_cleaned.csv": "beras_medium",
    "super1_cleaned.csv": "beras_premium",
    "super2_cleaned.csv": "beras_premium",
}


def _load_series(path: str):
    """Return {city_id: [(date, price), ...] sorted by date}."""
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df.sort_values("date")
    out: dict[str, list[tuple[datetime.date, float]]] = defaultdict(list)
    for cid, g in df.groupby(df["city_id"].astype(str)):
        out[cid] = list(zip(g["date"].tolist(), g["price_per_kg"].astype(float).tolist()))
    return out


def _score(series, horizon: int):
    """Holdout-backtest one series. Returns metrics dict or None if too short."""
    if len(series) < horizon + 60:
        return None
    train = series[:-horizon]
    test = series[-horizon:]                       # (date, actual)
    fc = _seasonal_naive_forecast(train, horizon=horizon)
    fc_by_date = {datetime.date.fromisoformat(r["date"]): r for r in fc}

    pairs = []
    cov_hits = 0
    for d, actual in test:
        r = fc_by_date.get(d)
        if r is None or actual <= 0:
            continue
        pred = r["point"]
        pairs.append((actual, pred))
        if r["p10"] <= actual <= r["p90"]:
            cov_hits += 1
    if not pairs:
        return None
    a = np.array([p[0] for p in pairs], dtype=float)
    f = np.array([p[1] for p in pairs], dtype=float)
    mape = float(np.mean(np.abs((a - f) / a)) * 100)
    mae = float(np.mean(np.abs(a - f)))
    rmse = float(np.sqrt(np.mean((a - f) ** 2)))
    cov = float(cov_hits / len(pairs) * 100)
    return {"n": len(pairs), "mape": mape, "mae": mae, "rmse": rmse, "coverage_80": cov}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=30)
    ap.add_argument("--json", default=None, help="optional path to dump full results")
    args = ap.parse_args()

    per_commodity: dict[str, list[dict]] = defaultdict(list)
    detail = []
    for fname, comm in FILE_COMMODITY.items():
        path = os.path.join(PRICE_DIR, fname)
        if not os.path.exists(path):
            continue
        series_by_city = _load_series(path)
        for cid, series in series_by_city.items():
            m = _score(series, args.horizon)
            if m is None:
                continue
            m2 = {"commodity": comm, "city_id": cid, "file": fname, **m}
            per_commodity[comm].append(m2)
            detail.append(m2)

    # aggregate per commodity (mean over cities) then overall (mean over commodities)
    print(f"\nHoldout backtest of DEPLOYED seasonal-naive forecaster "
          f"(horizon={args.horizon} days, leakage-free)\n")
    print(f"  {'Commodity':<16}{'series':>7}{'MAPE%':>9}{'MAE(Rp)':>11}{'RMSE(Rp)':>11}{'CI80%':>8}")
    print("  " + "-" * 60)
    comm_means = []
    for comm in sorted(per_commodity):
        rows = per_commodity[comm]
        mape = np.mean([r["mape"] for r in rows])
        mae = np.mean([r["mae"] for r in rows])
        rmse = np.mean([r["rmse"] for r in rows])
        cov = np.mean([r["coverage_80"] for r in rows])
        comm_means.append(mape)
        print(f"  {comm:<16}{len(rows):>7}{mape:>9.1f}{mae:>11,.0f}{rmse:>11,.0f}{cov:>7.0f}%")
    print("  " + "-" * 60)
    overall_mape = float(np.mean([r["mape"] for r in detail]))
    overall_cov = float(np.mean([r["coverage_80"] for r in detail]))
    print(f"  {'OVERALL (per-series mean)':<40}{overall_mape:>9.1f}{'':22}{overall_cov:>7.0f}%")
    print(f"\n  Series evaluated: {len(detail)} | commodities: {len(per_commodity)}\n")

    if args.json:
        os.makedirs(os.path.dirname(args.json), exist_ok=True)
        payload = {
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "method": "seasonal_naive_baseline",
            "horizon_days": args.horizon,
            "holdout": "last N calendar days, leakage-free",
            "overall_mape_pct": round(overall_mape, 2),
            "overall_ci80_coverage_pct": round(overall_cov, 1),
            "per_commodity": {
                c: {
                    "mape_pct": round(float(np.mean([r["mape"] for r in rows])), 2),
                    "mae_idr": round(float(np.mean([r["mae"] for r in rows])), 0),
                    "rmse_idr": round(float(np.mean([r["rmse"] for r in rows])), 0),
                    "ci80_coverage_pct": round(float(np.mean([r["coverage_80"] for r in rows])), 1),
                    "n_series": len(rows),
                }
                for c, rows in per_commodity.items()
            },
            "detail": detail,
        }
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        print(f"  Wrote {args.json}")


if __name__ == "__main__":
    main()
