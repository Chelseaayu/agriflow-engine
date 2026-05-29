"""
db/price_ingest.py — Offline vendor loader + Postgres ingest for PIHPS price history.

Three public functions:

    load_price_history_csvs(directory) -> list[dict]
        Read all *_cleaned.csv files from the vendored sample_data/price_history/
        directory.  Returns a list of normalised row dicts:
            {"date": datetime.date, "city_id": str, "commodity_code": str,
             "price_per_kg": float}
        Applies commodity_code normalisation (see COMMODITY_MAP below).
        Safe for offline/demo use — no network calls.

    ingest_to_postgres(rows, db_url) -> int
        Upsert rows into the price_history table.
        CODE-COMPLETE but GATED: raises RuntimeError unless the caller explicitly
        passes db_url.  Never called automatically.
        Returns the number of rows upserted.

    latest_prices(rows) -> dict[(city_id, commodity_code), price_per_kg]
        Given the list returned by load_price_history_csvs(), return a dict of
        the most-recent observed price per (city_id, commodity_code) pair.
        Used by the engine to replace synthetic Tier-1 prices with real data.

Commodity mapping rationale (documented in sample_data/price_history/SOURCE.md):
    cabe_rawit       -> cabai_rawit   (BI spelling normalisation)
    beras_medium_1   -> beras_medium  (PIHPS sub-grade → canonical)
    beras_medium_2   -> beras_medium  (PIHPS sub-grade → canonical)
    beras_super_1    -> beras_premium (PIHPS sub-grade → canonical)
    beras_super_2    -> beras_premium (PIHPS sub-grade → canonical)

When two sub-grades map to the same canonical code for the same (date, city_id),
their prices are averaged before the row is returned.  This preserves the UNIQUE
(date, city_id, commodity_code) constraint of the price_history table.
"""

from __future__ import annotations

import csv
import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Commodity code normalisation table
# Keys:   commodity_code values as they appear in Chelsea's CSV files
# Values: AgriFlow canonical codes (must match commodity.code in schema.sql)
# ---------------------------------------------------------------------------
COMMODITY_MAP: Dict[str, str] = {
    # Direct matches — no change needed, but listed explicitly for clarity
    "bawang_merah": "bawang_merah",
    "bawang_putih": "bawang_putih",
    "daging_ayam":  "daging_ayam",
    "telur_ayam":   "telur_ayam",
    # Spelling normalisation: Chelsea uses Indonesian colloquial 'cabe', engine uses BI 'cabai'
    "cabe_rawit":   "cabai_rawit",
    # Rice grade aggregation: PIHPS sub-grades → AgriFlow canonical grades
    "beras_medium_1": "beras_medium",
    "beras_medium_2": "beras_medium",
    "beras_super_1":  "beras_premium",
    "beras_super_2":  "beras_premium",
}

# Canonical codes that ENGINE knows about (subset of komoditas_constraints.csv
# that this dataset covers).  Used for validation.
KNOWN_ENGINE_CODES = frozenset(COMMODITY_MAP.values())


def load_price_history_csvs(directory: str | Path) -> List[Dict]:
    """
    Read all *_cleaned.csv files from `directory` and return normalised rows.

    Each returned dict has keys:
        date            datetime.date
        city_id         str   (e.g. "3509")
        commodity_code  str   (AgriFlow canonical, after COMMODITY_MAP lookup)
        price_per_kg    float

    When multiple source rows collapse to the same (date, city_id, commodity_code)
    after normalisation (e.g. beras_medium_1 + beras_medium_2 both map to
    beras_medium for the same date and city), the prices are averaged.

    Raises:
        FileNotFoundError  if directory does not exist
        ValueError         if a CSV row has an unrecognised commodity_code
                           (not in COMMODITY_MAP — strict, to catch schema drift)
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"Price history directory not found: {directory}")

    csv_files = sorted(directory.glob("*_cleaned.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No *_cleaned.csv files found in: {directory}")

    # Accumulate into (date, city_id, commodity_code) -> list[price]
    # so we can average when sub-grades collapse.
    accumulated: Dict[Tuple[datetime.date, str, str], List[float]] = {}

    for csv_path in csv_files:
        with csv_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for lineno, row in enumerate(reader, start=2):  # 1-indexed, header = line 1
                raw_code = row["commodity_code"].strip()
                canonical = COMMODITY_MAP.get(raw_code)
                if canonical is None:
                    raise ValueError(
                        f"{csv_path.name}:{lineno}: unrecognised commodity_code "
                        f"{raw_code!r} — add it to COMMODITY_MAP in db/price_ingest.py"
                    )

                date_val = datetime.date.fromisoformat(row["date"].strip())
                city_id = row["city_id"].strip()
                price = float(row["price_per_kg"].strip())

                key = (date_val, city_id, canonical)
                accumulated.setdefault(key, []).append(price)

    # Collapse to one row per key (average when multiple sub-grades present)
    rows: List[Dict] = []
    for (date_val, city_id, canonical), prices in accumulated.items():
        rows.append(
            {
                "date": date_val,
                "city_id": city_id,
                "commodity_code": canonical,
                "price_per_kg": sum(prices) / len(prices),
            }
        )

    # Sort for deterministic output (and nicer test assertions)
    rows.sort(key=lambda r: (r["commodity_code"], r["city_id"], r["date"]))
    return rows


def ingest_to_postgres(rows: List[Dict], db_url: str) -> int:
    """
    Upsert `rows` (as returned by load_price_history_csvs) into the
    price_history table.

    GATED: db_url must be a non-empty string.  Pass an explicit DSN — this
    function never reads environment variables, so callers stay in control.

    SQL used: INSERT ... ON CONFLICT (date, city_id, commodity_code) DO UPDATE
    so the operation is idempotent and safe to re-run.

    Returns the number of rows upserted.

    Requires: sqlalchemy + psycopg2-binary installed.
    """
    if not db_url or not db_url.strip():
        raise RuntimeError(
            "ingest_to_postgres() requires an explicit db_url (non-empty string). "
            "Pass the Supabase DSN directly — this function never reads env vars."
        )

    try:
        from sqlalchemy import create_engine, text  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "sqlalchemy is not installed. Run: pip install sqlalchemy psycopg2-binary"
        ) from exc

    engine = create_engine(db_url, pool_pre_ping=True, future=True)
    upsert_sql = text("""
        INSERT INTO price_history (date, city_id, commodity_code, price_per_kg, data_source)
        VALUES (:date, :city_id, :commodity_code, :price_per_kg, 'PIHPS')
        ON CONFLICT (date, city_id, commodity_code)
        DO UPDATE SET
            price_per_kg = EXCLUDED.price_per_kg,
            data_source  = EXCLUDED.data_source
    """)

    count = 0
    with engine.begin() as conn:
        for row in rows:
            conn.execute(
                upsert_sql,
                {
                    "date":           row["date"],
                    "city_id":        row["city_id"],
                    "commodity_code": row["commodity_code"],
                    "price_per_kg":   row["price_per_kg"],
                },
            )
            count += 1

    return count


def latest_prices(rows: List[Dict]) -> Dict[Tuple[str, str], float]:
    """
    Return the most-recent observed price per (city_id, commodity_code) pair.

    Input: the list returned by load_price_history_csvs().
    Output: dict[(city_id, commodity_code)] -> price_per_kg (float)

    "Most recent" is determined by the date field (datetime.date comparison).
    When multiple rows exist for the same key, the one with the latest date wins.

    Usage pattern (replacing synthetic Tier-1 prices in the engine):

        from db.price_ingest import load_price_history_csvs, latest_prices

        price_dir = Path("sample_data/price_history")
        rows = load_price_history_csvs(price_dir)
        latest = latest_prices(rows)

        # In the Tier-1 node builder:
        real_price = latest.get(
            (node.kabupaten.id, node.commodity.code),
            node.price_per_kg  # fallback: keep synthetic if no real data
        )
    """
    best: Dict[Tuple[str, str], Tuple[datetime.date, float]] = {}
    for row in rows:
        key = (row["city_id"], row["commodity_code"])
        date_val: datetime.date = row["date"]
        price: float = row["price_per_kg"]
        if key not in best or date_val > best[key][0]:
            best[key] = (date_val, price)

    return {k: v[1] for k, v in best.items()}
