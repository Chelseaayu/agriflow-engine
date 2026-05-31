"""
analysis/forecast_timesfm.py  --  Offline forecast precompute for AgriFlow.

ARCHITECTURE:
    This script runs OFFLINE (locally, not on HF Space) because TimesFM ~2GB
    model cannot be loaded on the free-tier Space (OOM).  The output JSON files
    are committed to the repo and the backend serves them at runtime without
    importing this module or timesfm.

HONESTY POLICY:
    If TimesFM cannot be loaded (not installed, network unavailable, Python
    version incompatible), this script falls back to a seasonal-naive baseline
    that is CLEARLY labelled in the output as "method": "seasonal_naive_baseline"
    so consumers can distinguish it from a genuine TimesFM forecast.

    DO NOT change the labelling.  If you want TimesFM output, fix the environment
    and re-run.

TIMESFM STATUS (2026-05-31):
    timesfm PyPI package (1.0.0) requires Python <=3.11 + jaxlib==0.4.26.
    This project runs Python 3.12+.  TimesFM 2.0 (PyTorch variant) is on
    HuggingFace Hub but requires the same pinned JAX+Flax stack via the PyPI
    package.  Install blocker is hard on Python 3.12/3.14.

    To use real TimesFM:
      1. Run this script with Python 3.11: `py -3.11 analysis/forecast_timesfm.py`
      2. Or wait for timesfm to release a Python 3.12-compatible wheel.
      3. Check for a conda-based install path: `conda install -c conda-forge timesfm`

USAGE:
    # With TimesFM (Python 3.11 + timesfm installed):
    python analysis/forecast_timesfm.py

    # Explicit baseline (any Python):
    python analysis/forecast_timesfm.py --method baseline

OUTPUT:
    sample_data/forecasts/forecast_all.json  --  one file, all series

FORECAST SCHEMA (per record):
    commodity_code   str
    city_id          str
    city_name        str
    method           str  ("timesfm_2.0" | "seasonal_naive_baseline")
    generated_at     str  ISO 8601 UTC
    horizon_days     int  (30)
    history_end_date str  ISO 8601 -- last observed date
    forecasts:  list of {
        date   str  ISO 8601
        point  float   (IDR/kg, point forecast)
        p10    float   (IDR/kg, 10th percentile)
        p90    float   (IDR/kg, 90th percentile)
    }
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.price_anomaly import _load_all_rows, CITY_NAMES

HORIZON = 30


# ---------------------------------------------------------------------------
# Seasonal-naive baseline (transparent fallback -- NOT TimesFM)
# ---------------------------------------------------------------------------

def _seasonal_naive_forecast(
    series: list[tuple[datetime.date, float]],
    horizon: int = HORIZON,
) -> list[dict[str, Any]]:
    """
    Seasonal-naive: for day h, predict = median of same-calendar-month prices
    observed in the training series.

    Uncertainty band: +/- 1 MAD of the same-month observations.

    This is a statistical method, not a foundation model.  It is labelled as
    "seasonal_naive_baseline" everywhere it appears.
    """
    import numpy as np

    prices = [p for _, p in series]
    dates  = [d for d, _ in series]
    arr    = np.array(prices, dtype=float)

    # Build per-month (median, MAD) from the last 2 years of observed data
    cutoff = dates[-1] - datetime.timedelta(days=2 * 365)
    recent = [(d, p) for d, p in series if d >= cutoff]
    if len(recent) < 30:
        recent = series  # fall back to full series for short series

    month_stats: dict[int, tuple[float, float]] = {}
    from collections import defaultdict
    month_vals: dict[int, list[float]] = defaultdict(list)
    for d, p in recent:
        month_vals[d.month].append(p)
    for m, vals in month_vals.items():
        v = np.array(vals)
        med = float(np.median(v))
        mad = float(np.median(np.abs(v - med)))
        month_stats[m] = (med, mad)

    # Overall fallback stats
    overall_med = float(np.median(arr[-30:]))
    overall_mad = float(np.median(np.abs(arr[-30:] - overall_med)))

    last_date = dates[-1]
    result = []
    for h in range(1, horizon + 1):
        target_date = last_date + datetime.timedelta(days=h)
        med, mad = month_stats.get(target_date.month, (overall_med, overall_mad))
        # CI: +/- 1.4826 * MAD (same scaling as the anomaly detector)
        ci_half = 1.4826 * mad if mad > 0 else 0.05 * med
        result.append({
            "date":  target_date.isoformat(),
            "point": round(med, 2),
            "p10":   round(max(0, med - ci_half), 2),
            "p90":   round(med + ci_half, 2),
        })
    return result


# ---------------------------------------------------------------------------
# TimesFM path (gated on successful import)
# ---------------------------------------------------------------------------

def _timesfm_available() -> bool:
    try:
        import timesfm  # noqa: F401
        return True
    except ImportError:
        return False


def _timesfm_forecast(
    series: list[tuple[datetime.date, float]],
    horizon: int = HORIZON,
    model_path: str = "google/timesfm-2.0-500m-pytorch",
) -> list[dict[str, Any]]:
    """
    Run TimesFM 2.0 (PyTorch variant) on one price series.
    Loads the model on first call (expensive — ~2 GB download + load).
    Caller must ensure timesfm is installed and Python 3.10/3.11 is active.
    """
    import timesfm
    import numpy as np

    prices = np.array([p for _, p in series], dtype=float)
    dates  = [d for d, _ in series]

    # TimesFM 2.0 PyTorch API
    tfm = timesfm.TimesFm(
        hparams=timesfm.TimesFmHparams(
            backend="cpu",
            per_core_batch_size=1,
            horizon_len=horizon,
            num_heads=16,
            use_positional_embedding=False,
        ),
        checkpoint=timesfm.TimesFmCheckpoint(
            huggingface_repo_id=model_path,
        ),
    )

    forecast_input = [prices]
    freq           = [0]  # 0 = high-frequency (daily)

    _, quantile_forecasts = tfm.forecast(
        forecast_input,
        freq=freq,
        quantile_levels=[0.1, 0.5, 0.9],
    )

    # quantile_forecasts shape: (batch=1, horizon, 3)
    qf = quantile_forecasts[0]  # (horizon, 3)
    last_date = dates[-1]
    result = []
    for h in range(horizon):
        target_date = last_date + datetime.timedelta(days=h + 1)
        p10   = float(qf[h, 0])
        point = float(qf[h, 1])
        p90   = float(qf[h, 2])
        result.append({
            "date":  target_date.isoformat(),
            "point": round(point, 2),
            "p10":   round(max(0, p10), 2),
            "p90":   round(p90, 2),
        })
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(
    price_dir: Path,
    out_dir: Path,
    method: str,
    model_path: str,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "forecast_all.json"

    # Determine actual method
    if method == "auto":
        if _timesfm_available():
            method = "timesfm"
            print("TimesFM detected — will use real model.")
        else:
            method = "baseline"
            print(
                "WARNING: timesfm not importable on this Python version.\n"
                "Falling back to seasonal_naive_baseline.\n"
                "To get real TimesFM output, run with Python 3.10 or 3.11 + timesfm installed.\n"
                "The output JSON will be labelled method=seasonal_naive_baseline."
            )

    generated_at = datetime.datetime.utcnow().isoformat() + "Z"
    series_map   = _load_all_rows(price_dir)

    print(f"Forecasting {len(series_map)} series ...")
    all_records: list[dict[str, Any]] = []

    for (commodity, city), series in sorted(series_map.items()):
        if len(series) < 30:
            print(f"  Skipping {commodity}/{city}: too short ({len(series)} obs)")
            continue

        if method == "timesfm":
            try:
                fc_points = _timesfm_forecast(series, horizon=HORIZON, model_path=model_path)
                method_label = "timesfm_2.0"
            except Exception as exc:
                print(f"  TimesFM failed for {commodity}/{city}: {exc} — using baseline")
                fc_points    = _seasonal_naive_forecast(series, horizon=HORIZON)
                method_label = "seasonal_naive_baseline"
        else:
            fc_points    = _seasonal_naive_forecast(series, horizon=HORIZON)
            method_label = "seasonal_naive_baseline"

        all_records.append({
            "commodity_code":   commodity,
            "city_id":          city,
            "city_name":        CITY_NAMES.get(city, city),
            "method":           method_label,
            "generated_at":     generated_at,
            "horizon_days":     HORIZON,
            "history_end_date": series[-1][0].isoformat(),
            "forecasts":        fc_points,
        })
        print(f"  {commodity}/{city}: {method_label} — last obs {series[-1][0]}")

    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(all_records, fh, ensure_ascii=False, separators=(",", ":"))

    size_kb = out_path.stat().st_size / 1024
    print(f"\nWrote {len(all_records)} series forecasts to {out_path}  ({size_kb:.1f} KB)")
    if any(r["method"] == "seasonal_naive_baseline" for r in all_records):
        print(
            "\nNOTE: Output labelled 'seasonal_naive_baseline'.  "
            "This is a transparent statistical baseline, NOT TimesFM.  "
            "Re-run with Python 3.10/3.11 + timesfm installed for real forecasts."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Precompute 30-day forecasts (TimesFM or seasonal baseline)."
    )
    parser.add_argument(
        "--price-dir",
        type=Path,
        default=ROOT / "sample_data" / "price_history",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "sample_data" / "forecasts",
    )
    parser.add_argument(
        "--method",
        choices=["auto", "timesfm", "baseline"],
        default="auto",
        help=(
            "auto: use TimesFM if available, else baseline. "
            "baseline: force seasonal_naive_baseline (honest fallback). "
            "timesfm: force TimesFM (will fail if not installed)."
        ),
    )
    parser.add_argument(
        "--model",
        default="google/timesfm-2.0-500m-pytorch",
        help="HuggingFace model ID for TimesFM 2.0 PyTorch variant.",
    )
    args = parser.parse_args()
    main(args.price_dir, args.out_dir, args.method, args.model)
