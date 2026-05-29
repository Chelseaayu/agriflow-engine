"""
db/db_loader.py — Postgres/Supabase backend for AgriFlow data.

Mirrors the exact return signature of sample_data.loader.load_all_sample_data()
so the two loaders are drop-in substitutes behind the DATA_BACKEND env flag.

Return dict keys (same as CSV loader):
    kabupaten        -> Dict[str, Kabupaten]
    komoditas        -> Dict[str, Commodity]
    surplus          -> List[SupplyNode]
    deficit          -> List[DemandNode]
    weather          -> Dict[str, WeatherForecast]
    historical_prices -> Dict[str, Tuple[float, float]]

Requires SUPABASE_DB_URL env var (postgresql+psycopg2://user:pass@host:port/db).
Raises RuntimeError immediately if the env var is absent so the caller sees a
clear error rather than a confusing connection exception later.

Usage (when creds are live):
    import os
    os.environ["SUPABASE_DB_URL"] = "postgresql+psycopg2://postgres:<pw>@<host>:5432/postgres"

    from db.db_loader import load_all
    data = load_all()
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# SQLAlchemy import — optional at module-import time so the package stays
# importable on installs that don't have sqlalchemy yet (test (b) just needs
# the RuntimeError path, not an ImportError).
# ---------------------------------------------------------------------------
try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import Engine
    _SQLALCHEMY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SQLALCHEMY_AVAILABLE = False

from matching_engine.models import (
    Commodity,
    DemandNode,
    Kabupaten,
    SupplyNode,
    Tier,
    WeatherForecast,
)

_ENV_KEY = "SUPABASE_DB_URL"


def _require_db_url() -> str:
    """Return the DB URL or raise a clear RuntimeError."""
    url = os.environ.get(_ENV_KEY, "").strip()
    if not url:
        raise RuntimeError(
            f"Postgres backend requested but {_ENV_KEY!r} env var is not set. "
            "Set it to a valid DSN, e.g.:\n"
            "  postgresql+psycopg2://postgres:<password>@<host>:5432/postgres\n"
            "Or switch to the CSV backend by setting DATA_BACKEND=csv (default)."
        )
    return url


def _get_engine() -> "Engine":
    # Check env var first so operators get a clear "set SUPABASE_DB_URL" message
    # even when sqlalchemy is not yet installed.
    url = _require_db_url()
    if not _SQLALCHEMY_AVAILABLE:
        raise RuntimeError(  # pragma: no cover
            "sqlalchemy is not installed. Run: pip install sqlalchemy psycopg2-binary"
        )
    return create_engine(url, pool_pre_ping=True, future=True)


# ---------------------------------------------------------------------------
# Per-table loaders
# ---------------------------------------------------------------------------

def _load_kabupaten(engine: "Engine") -> Dict[str, Kabupaten]:
    query = text("""
        SELECT kab_id, nama, latitude, longitude, ipm_2024, population_2024, tier
        FROM kabupaten
        ORDER BY kab_id
    """)
    out: Dict[str, Kabupaten] = {}
    with engine.connect() as conn:
        rows = conn.execute(query).fetchall()
    for row in rows:
        tier = Tier.HIGH if row.tier == "TIER_1_HIGH" else Tier.MEDIUM
        out[row.kab_id] = Kabupaten(
            id=row.kab_id,
            nama=row.nama,
            latitude=float(row.latitude),
            longitude=float(row.longitude),
            ipm=float(row.ipm_2024),
            tier=tier,
            population=int(row.population_2024),
        )
    return out


def _load_komoditas(engine: "Engine") -> Dict[str, Commodity]:
    query = text("""
        SELECT code, nama, max_distance_km, min_viable_tons, max_fresh_age_days
        FROM commodity
        ORDER BY code
    """)
    out: Dict[str, Commodity] = {}
    with engine.connect() as conn:
        rows = conn.execute(query).fetchall()
    for row in rows:
        out[row.code] = Commodity(
            code=row.code,
            nama=row.nama,
            max_distance_km=float(row.max_distance_km),
            min_viable_tons=float(row.min_viable_tons),
            max_fresh_age_days=int(row.max_fresh_age_days),
        )
    return out


def _load_surplus_deficit(
    engine: "Engine",
    kabupaten: Dict[str, Kabupaten],
    komoditas: Dict[str, Commodity],
) -> Tuple[List[SupplyNode], List[DemandNode]]:
    query = text("""
        SELECT kab_id, commodity_code, role, volume_tons,
               price_idr_per_kg, harvest_age_days
        FROM surplus_deficit
        ORDER BY kab_id, commodity_code
    """)
    surplus: List[SupplyNode] = []
    deficit: List[DemandNode] = []
    now = datetime.now()
    with engine.connect() as conn:
        rows = conn.execute(query).fetchall()
    for row in rows:
        kab = kabupaten[row.kab_id]
        komo = komoditas[row.commodity_code]
        if row.role == "SURPLUS":
            surplus.append(SupplyNode(
                kabupaten=kab,
                commodity=komo,
                volume_tons=float(row.volume_tons),
                price_per_kg=float(row.price_idr_per_kg),
                harvest_age_days=int(row.harvest_age_days),
                timestamp=now,
                data_source="POSTGRES",
            ))
        elif row.role == "DEFICIT":
            deficit.append(DemandNode(
                kabupaten=kab,
                commodity=komo,
                volume_tons=float(row.volume_tons),
                price_per_kg=float(row.price_idr_per_kg),
                timestamp=now,
                data_source="POSTGRES",
            ))
        else:
            raise ValueError(f"Unknown role in surplus_deficit table: {row.role!r}")
    return surplus, deficit


def _load_weather(engine: "Engine") -> Dict[str, WeatherForecast]:
    query = text("""
        SELECT origin_kab_id, dest_kab_id, max_rain_mm, transit_window_days, source
        FROM weather_forecast
        ORDER BY origin_kab_id, dest_kab_id
    """)
    out: Dict[str, WeatherForecast] = {}
    with engine.connect() as conn:
        rows = conn.execute(query).fetchall()
    for row in rows:
        key = f"{row.origin_kab_id}_{row.dest_kab_id}"
        out[key] = WeatherForecast(
            origin_kab_id=row.origin_kab_id,
            dest_kab_id=row.dest_kab_id,
            max_rain_mm=float(row.max_rain_mm),
            transit_window_days=int(row.transit_window_days),
            source=row.source,
        )
    return out


def _load_historical_prices(engine: "Engine") -> Dict[str, Tuple[float, float]]:
    query = text("""
        SELECT commodity_code, median_idr_per_kg, std_idr_per_kg
        FROM historical_prices
        ORDER BY commodity_code
    """)
    out: Dict[str, Tuple[float, float]] = {}
    with engine.connect() as conn:
        rows = conn.execute(query).fetchall()
    for row in rows:
        out[row.commodity_code] = (
            float(row.median_idr_per_kg),
            float(row.std_idr_per_kg),
        )
    return out


# ---------------------------------------------------------------------------
# Public API — mirrors sample_data.loader.load_all_sample_data() exactly
# ---------------------------------------------------------------------------

def load_all() -> dict:
    """
    Load all AgriFlow reference data from Postgres.

    Return dict with keys:
        kabupaten, komoditas, surplus, deficit, weather, historical_prices

    Raises RuntimeError if SUPABASE_DB_URL is not set.
    """
    engine = _get_engine()
    kab = _load_kabupaten(engine)
    komo = _load_komoditas(engine)
    surplus, deficit = _load_surplus_deficit(engine, kab, komo)
    weather = _load_weather(engine)
    historical = _load_historical_prices(engine)
    return {
        "kabupaten": kab,
        "komoditas": komo,
        "surplus": surplus,
        "deficit": deficit,
        "weather": weather,
        "historical_prices": historical,
    }
