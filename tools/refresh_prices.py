"""
tools/refresh_prices.py -- Append new PIHPS observations to the vendored
price history without corrupting it.

WHY THIS SHAPE
--------------
data_sources/pihps_bi.py's live scraper is still a placeholder that falls
back to mock rows when the site cannot be parsed. Silently appending mock
rows to sample_data/price_history/ would poison the anomaly scan and the
forecast calibration, so this tool only writes rows it can trust:

  * --input FILE   a CSV exported from PIHPS (or from the team's cleaning
                   pipeline) with columns date,city_id,commodity_code,price_per_kg
  * --live         call PIHPSConnector(real_scrape=True) and write ONLY if
                   every returned row carries source == "PIHPS" (never
                   "PIHPS_MOCK"). Until the scraper is finished this path
                   exits 0 with "nothing written" so the daily workflow stays
                   green and honest.

Rows are matched to the existing *_cleaned.csv file by commodity_code and
de-duplicated on (date, city_id, commodity_code). Nothing is rewritten; new
rows are appended in date order at the end of each file.

Usage:
    python tools/refresh_prices.py --input pihps_export.csv
    python tools/refresh_prices.py --live
    python tools/refresh_prices.py --input x.csv --dry-run
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PRICE_DIR = ROOT / "sample_data" / "price_history"

# Raw code as written in the CSV files -> file name. Mirrors the mapping in
# analysis/price_anomaly.py and db/price_ingest.py.
FILE_FOR_CODE: Dict[str, str] = {
    "bawang_merah": "bawang_merah_cleaned.csv",
    "bawang_putih": "bawang_putih_cleaned.csv",
    "cabe_rawit": "cabe_rawit_cleaned.csv",
    "cabai_rawit": "cabe_rawit_cleaned.csv",
    "daging_ayam": "daging_ayam_cleaned.csv",
    "telur_ayam": "telur_ayam_cleaned.csv",
    "beras_medium_1": "medium1_cleaned.csv",
    "beras_medium_2": "medium2_cleaned.csv",
    "beras_super_1": "super1_cleaned.csv",
    "beras_super_2": "super2_cleaned.csv",
}
# Code written into the file (the files keep their own spelling).
CODE_IN_FILE: Dict[str, str] = {
    "cabai_rawit": "cabe_rawit",
}
TIER1_CITIES = {"3509", "3510", "3529", "3571", "3573", "3574", "3577", "3578"}

Row = Tuple[str, str, str, float]  # date, city_id, code_in_file, price


def _validate(rows: Iterable[dict]) -> List[Row]:
    out: List[Row] = []
    for r in rows:
        try:
            d = dt.date.fromisoformat(str(r["date"])[:10]).isoformat()
            city = str(r["city_id"]).strip()
            code = str(r["commodity_code"]).strip()
            price = float(r["price_per_kg"])
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError(f"bad row {r!r}: {exc}") from exc
        if code not in FILE_FOR_CODE:
            continue  # commodity the history does not track
        if city not in TIER1_CITIES:
            continue  # history is the 8 IHK cities only
        if price <= 0:
            raise ValueError(f"non-positive price in row {r!r}")
        out.append((d, city, CODE_IN_FILE.get(code, code), price))
    return out


def _existing_keys(path: Path) -> set:
    keys = set()
    if not path.exists():
        return keys
    with path.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            keys.add((r["date"].strip(), r["city_id"].strip(), r["commodity_code"].strip()))
    return keys


def append_rows(rows: List[Row], price_dir: Path = PRICE_DIR, dry_run: bool = False) -> Dict[str, int]:
    """Append de-duplicated rows to the right files. Returns {file: n_added}."""
    by_file: Dict[str, List[Row]] = {}
    for d, city, code, price in rows:
        raw_code = next(k for k, v in CODE_IN_FILE.items() if v == code) if code in CODE_IN_FILE.values() else code
        fname = FILE_FOR_CODE[raw_code]
        by_file.setdefault(fname, []).append((d, city, code, price))

    added: Dict[str, int] = {}
    for fname, frows in by_file.items():
        path = price_dir / fname
        seen = _existing_keys(path)
        new = sorted({r for r in frows if (r[0], r[1], r[2]) not in seen}, key=lambda r: (r[0], r[1]))
        added[fname] = len(new)
        if dry_run or not new:
            continue
        write_header = not path.exists() or path.stat().st_size == 0
        with path.open("a", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            if write_header:
                w.writerow(["date", "city_id", "commodity_code", "price_per_kg"])
            for d, city, code, price in new:
                w.writerow([d, city, code, int(price) if float(price).is_integer() else price])
    return added


def rows_from_csv(path: Path) -> List[Row]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return _validate(csv.DictReader(fh))


def rows_from_live() -> List[Row]:
    from data_sources.pihps_bi import PIHPSConnector
    fetched = PIHPSConnector(real_scrape=True).fetch_today()
    if not fetched:
        return []
    if any(r.get("source") != "PIHPS" for r in fetched):
        print("live fetch returned mock or fallback rows; refusing to write them", file=sys.stderr)
        return []
    today = dt.date.today().isoformat()
    return _validate({
        "date": today, "city_id": r["kabupaten_id"],
        "commodity_code": r["commodity_code"], "price_per_kg": r["price_per_kg"],
    } for r in fetched)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--input", type=Path, help="CSV with date,city_id,commodity_code,price_per_kg")
    ap.add_argument("--live", action="store_true", help="fetch via PIHPSConnector(real_scrape=True)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not args.input and not args.live:
        ap.error("give --input FILE or --live")

    rows: List[Row] = []
    if args.input:
        rows += rows_from_csv(args.input)
    if args.live:
        rows += rows_from_live()
    if not rows:
        print("nothing written (no trusted rows)")
        return 0
    added = append_rows(rows, dry_run=args.dry_run)
    total = sum(added.values())
    for f, n in sorted(added.items()):
        print(f"  {f}: +{n}{' (dry run)' if args.dry_run else ''}")
    print(f"{'would add' if args.dry_run else 'added'} {total} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
