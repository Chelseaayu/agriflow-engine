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

TIMESFM STATUS (2026-08-10):
    This project uses the installed ``timesfm`` package's TimesFM 2.5 PyTorch
    adapter. The package can run on the project's Python 3.12 environment when
    its PyTorch dependencies are present. The first real forecast downloads the
    ``google/timesfm-2.5-200m-pytorch`` weights if they are not already cached.

    To use real TimesFM:
      1. Run this script with the project virtual environment and ``--method auto``.
      2. Keep enough free RAM and disk space for model download and CPU inference.
      3. Use ``--method baseline`` only when an explicit statistical fallback is wanted.

USAGE:
    # Auto-select TimesFM 2.5 when the installed adapter is available:
    .venv\\Scripts\\python.exe analysis/forecast_timesfm.py --method auto

    # Explicit baseline (any Python):
    .venv\\Scripts\\python.exe analysis/forecast_timesfm.py --method baseline

OUTPUT:
    sample_data/forecasts/forecast_all.json  --  one file, all series

FORECAST SCHEMA (per record):
    commodity_code   str
    city_id          str
    city_name        str
    method           str  ("timesfm_2.5" | "seasonal_naive_baseline")
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
import csv
import datetime
import functools
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.price_ingest import (
    PIHPS_SOURCE,
    SISKAPERBAPO_SOURCE,
    load_source_price_history_csvs,
    select_active_prices,
)

HORIZON = 30
ACTIVE_SOURCE_POLICY = "SISKAPERBAPO_EXACT_KEY_THEN_PIHPS"
KABUPATEN_REFERENCE_PATH = ROOT / "sample_data" / "kabupaten_jatim.csv"


def _load_active_series(price_dir: Path) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Load source-aware prices, select active rows, and group them by series.

    Siskaperbapo precedence and PIHPS fallback are delegated exclusively to the
    public price-loader contract. Each returned row remains an observed active
    price with its selected source provenance.
    """
    source_records = load_source_price_history_csvs(price_dir)
    active_records = select_active_prices(source_records)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in active_records:
        grouped[(row["commodity_code"], row["city_id"])].append(row)

    ordered: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for key in sorted(grouped):
        ordered[key] = sorted(grouped[key], key=lambda row: row["date"])
    return ordered


@functools.lru_cache(maxsize=1)
def _load_city_names(
    reference_path: Path = KABUPATEN_REFERENCE_PATH,
) -> dict[str, str]:
    """Return Kabupaten/Kota labels from the 38-region reference dataset."""
    with reference_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required_columns = {"kab_id", "nama"}
        missing = required_columns - set(reader.fieldnames or ())
        if missing:
            names = ", ".join(sorted(missing))
            raise ValueError(f"{reference_path}: missing required columns: {names}")
        city_names = {
            row["kab_id"].strip(): row["nama"].strip()
            for row in reader
            if row["kab_id"].strip() and row["nama"].strip()
        }
    return city_names


def _history_metadata(active_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Describe the actual selected observations used by one forecast series."""
    if not active_rows:
        raise ValueError("Cannot build history metadata for an empty active series")

    start_date = active_rows[0]["date"]
    end_date = active_rows[-1]["date"]
    observation_count = len(active_rows)
    calendar_days = (end_date - start_date).days + 1
    coverage_ratio = round(observation_count / calendar_days, 6)
    if coverage_ratio >= 0.90:
        coverage_confidence = "HIGH"
    elif coverage_ratio >= 0.70:
        coverage_confidence = "MEDIUM"
    else:
        coverage_confidence = "LOW"

    source_counts = {
        source: sum(row["data_source"] == source for row in active_rows)
        for source in (SISKAPERBAPO_SOURCE, PIHPS_SOURCE)
    }
    return {
        "active_source_policy": ACTIVE_SOURCE_POLICY,
        "history_start_date": start_date.isoformat(),
        "history_observation_count": observation_count,
        "active_history_source_counts": source_counts,
        "latest_observation_source": active_rows[-1]["data_source"],
        "history_coverage_ratio": coverage_ratio,
        "history_coverage_confidence": coverage_confidence,
    }


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
    """Return whether the installed TimesFM 2.5 PyTorch adapter is importable."""
    try:
        from timesfm.timesfm_2p5.timesfm_2p5_torch import TimesFM_2p5_200M_torch  # noqa: F401
        return True
    except (ImportError, ModuleNotFoundError):
        return False


@functools.lru_cache(maxsize=1)
def _load_timesfm_model(model_path: str):
    """Load and configure the TimesFM 2.5 model once for the entire run."""
    from timesfm import ForecastConfig
    from timesfm.timesfm_2p5.timesfm_2p5_torch import TimesFM_2p5_200M_torch

    model = TimesFM_2p5_200M_torch.from_pretrained(
        model_path,
        torch_compile=False,
    )
    model.compile(
        ForecastConfig(
            max_context=2048,
            max_horizon=HORIZON,
            per_core_batch_size=1,
            # Keep the public quantile channels monotonic around the central
            # (P50) forecast that the adapter returns as its point forecast.
            fix_quantile_crossing=True,
        )
    )
    return model


def _timesfm_forecast(
    series: list[tuple[datetime.date, float]],
    horizon: int = HORIZON,
    model_path: str = "google/timesfm-2.5-200m-pytorch",
) -> list[dict[str, Any]]:
    """Run the installed TimesFM 2.5 PyTorch API on one price series.

    The model is cached after its first load. The 2.5 API returns a dedicated
    point forecast (its public P50 output) plus ten output channels. Channel 0
    is not a quantile; the ordered P10/P50/P90 channels are 1/5/9.
    """
    import numpy as np

    prices = np.array([price for _, price in series], dtype=float)
    dates = [observation_date for observation_date, _ in series]
    point_forecasts, quantile_forecasts = _load_timesfm_model(model_path).forecast(
        horizon=horizon,
        inputs=[prices],
    )

    points = point_forecasts[0]
    quantiles = quantile_forecasts[0]
    result = []
    for index in range(horizon):
        target_date = dates[-1] + datetime.timedelta(days=index + 1)
        p10 = float(quantiles[index, 1])
        point = float(points[index])
        p90 = float(quantiles[index, 9])
        result.append({
            "date": target_date.isoformat(),
            "point": round(point, 2),
            "p10": round(max(0, p10), 2),
            "p90": round(p90, 2),
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
                "WARNING: the TimesFM 2.5 PyTorch adapter is not importable.\n"
                "Falling back to seasonal_naive_baseline.\n"
                "Install a compatible timesfm package with its PyTorch dependencies, then re-run with --method auto.\n"
                "The output JSON will be labelled method=seasonal_naive_baseline."
            )

    generated_at = datetime.datetime.utcnow().isoformat() + "Z"
    city_names = _load_city_names()
    series_map = _load_active_series(price_dir)

    print(f"Forecasting {len(series_map)} active-price series ...")
    all_records: list[dict[str, Any]] = []

    for (commodity, city), active_rows in series_map.items():
        series = [(row["date"], row["price_per_kg"]) for row in active_rows]
        if len(series) < 30:
            print(f"  Skipping {commodity}/{city}: too short ({len(series)} obs)")
            continue

        if method == "timesfm":
            try:
                fc_points = _timesfm_forecast(series, horizon=HORIZON, model_path=model_path)
                method_label = "timesfm_2.5"
            except Exception as exc:
                print(f"  TimesFM failed for {commodity}/{city}: {exc} — using baseline")
                fc_points = _seasonal_naive_forecast(series, horizon=HORIZON)
                method_label = "seasonal_naive_baseline"
        else:
            fc_points = _seasonal_naive_forecast(series, horizon=HORIZON)
            method_label = "seasonal_naive_baseline"

        all_records.append({
            "commodity_code": commodity,
            "city_id": city,
            "city_name": city_names.get(city, city),
            "method": method_label,
            "generated_at": generated_at,
            "horizon_days": HORIZON,
            "history_end_date": series[-1][0].isoformat(),
            "forecasts": fc_points,
            **_history_metadata(active_rows),
        })
        print(
            f"  {commodity}/{city}: {method_label} — "
            f"last obs {series[-1][0]} ({active_rows[-1]['data_source']})"
        )

    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(all_records, fh, ensure_ascii=False, separators=(",", ":"))

    size_kb = out_path.stat().st_size / 1024
    print(f"\nWrote {len(all_records)} series forecasts to {out_path}  ({size_kb:.1f} KB)")
    if any(r["method"] == "seasonal_naive_baseline" for r in all_records):
        print(
            "\nNOTE: Output labelled 'seasonal_naive_baseline'.  "
            "This is a transparent statistical baseline, NOT TimesFM.  "
            "Re-run with --method auto after installing the TimesFM 2.5 PyTorch adapter for real forecasts."
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
        default="google/timesfm-2.5-200m-pytorch",
        help="HuggingFace model ID for the installed TimesFM 2.5 PyTorch adapter.",
    )
    args = parser.parse_args()
    main(args.price_dir, args.out_dir, args.method, args.model)
