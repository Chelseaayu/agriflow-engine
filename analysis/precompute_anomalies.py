"""
analysis/precompute_anomalies.py  --  Precompute all S-H-ESD anomalies to JSON.

Run offline (locally or in CI) to produce sample_data/anomalies/anomalies_all.json.
The backend serves from this file at runtime -- zero runtime computation on HF Space.

Usage:
    python analysis/precompute_anomalies.py
    python analysis/precompute_anomalies.py --price-dir sample_data/price_history
                                             --out-dir sample_data/anomalies

Output schema per record:
    date           str (ISO 8601, YYYY-MM-DD)
    price          float
    rolling_median float
    deviation_pct  float
    type           str  ("SPIKE" | "DROP")
    score          float
    commodity_code str
    city_id        str
    city_name      str
    persistent     bool
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.price_anomaly import scan_all, CITY_NAMES


def main(price_dir: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "anomalies_all.json"

    print(f"Scanning {price_dir} ...")
    anomalies = scan_all(price_dir, window=30, k=3.0, trend_window=30, persist=2)
    print(f"  Found {len(anomalies)} anomalies across all series.")

    # Serialise: convert datetime.date -> str, numpy floats -> float
    records = []
    for a in anomalies:
        records.append({
            "date":           a["date"].isoformat(),
            "price":          float(a["price"]),
            "rolling_median": float(a["rolling_median"]),
            "deviation_pct":  float(a["deviation_pct"]),
            "type":           a["type"],
            "score":          float(a["score"]),
            "commodity_code": a["commodity_code"],
            "city_id":        a["city_id"],
            "city_name":      CITY_NAMES.get(a["city_id"], a["city_id"]),
            "persistent":     bool(a["persistent"]),
        })

    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, separators=(",", ":"))

    size_kb = out_path.stat().st_size / 1024
    print(f"  Wrote {len(records)} records to {out_path}  ({size_kb:.1f} KB)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Precompute S-H-ESD anomaly scan to JSON.")
    parser.add_argument(
        "--price-dir",
        type=Path,
        default=ROOT / "sample_data" / "price_history",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "sample_data" / "anomalies",
    )
    args = parser.parse_args()
    main(args.price_dir, args.out_dir)
