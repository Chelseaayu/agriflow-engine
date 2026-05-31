"""
Data Loader — CSV → Engine Objects
====================================

Transform sample CSV ke SupplyNode, DemandNode, Kabupaten, dst.
Tim bisa pakai loader ini sebagai template saat integrate dengan data real
(PIHPS scraper, Bapanas API, dll).

Usage:

    from sample_data.loader import load_all_sample_data

    data = load_all_sample_data()
    surplus_nodes = data["surplus"]
    deficit_nodes = data["deficit"]
    weather = data["weather"]
    historical = data["historical_prices"]
"""

from __future__ import annotations
import csv
import os
from datetime import datetime
from typing import Dict, List, Tuple

from matching_engine.models import (
    Commodity, DemandNode, Kabupaten, SupplyNode, Tier, WeatherForecast,
)


SAMPLE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_kabupaten() -> Dict[str, Kabupaten]:
    """Load 38 kabupaten Jatim dari kabupaten_jatim.csv."""
    path = os.path.join(SAMPLE_DIR, "kabupaten_jatim.csv")
    out: Dict[str, Kabupaten] = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tier = Tier.HIGH if row["tier"] == "TIER_1_HIGH" else Tier.MEDIUM
            out[row["kab_id"]] = Kabupaten(
                id=row["kab_id"],
                nama=row["nama"],
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
                ipm=float(row["ipm_2024"]),
                tier=tier,
                population=int(row["population_2024"]),
            )
    return out


def load_komoditas() -> Dict[str, Commodity]:
    """Load 19 komoditas dari komoditas_constraints.csv."""
    path = os.path.join(SAMPLE_DIR, "komoditas_constraints.csv")
    out: Dict[str, Commodity] = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            out[row["code"]] = Commodity(
                code=row["code"],
                nama=row["nama"],
                max_distance_km=float(row["max_distance_km"]),
                min_viable_tons=float(row["min_viable_tons"]),
                max_fresh_age_days=int(row["max_fresh_age_days"]),
            )
    return out


def load_surplus_deficit(
    kabupaten: Dict[str, Kabupaten],
    komoditas: Dict[str, Commodity],
    *,
    csv_filename: str = "surplus_deficit.csv",
) -> Tuple[List[SupplyNode], List[DemandNode]]:
    """Load surplus & deficit dari surplus_deficit.csv (or a named override).

    Args:
        kabupaten:    dict of Kabupaten objects keyed by kab_id.
        komoditas:    dict of Commodity objects keyed by code.
        csv_filename: filename within SAMPLE_DIR to load.
                      Defaults to the canonical "surplus_deficit.csv".
                      Pass "surplus_deficit_constrained.csv" for the
                      La Nina supply-shock scenario.
    """
    path = os.path.join(SAMPLE_DIR, csv_filename)
    surplus: List[SupplyNode] = []
    deficit: List[DemandNode] = []
    now = datetime.now()
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            kab = kabupaten[row["kab_id"]]
            komo = komoditas[row["commodity_code"]]
            if row["role"] == "SURPLUS":
                surplus.append(SupplyNode(
                    kabupaten=kab, commodity=komo,
                    volume_tons=float(row["volume_tons"]),
                    price_per_kg=float(row["price_idr_per_kg"]),
                    harvest_age_days=int(row["harvest_age_days"]),
                    timestamp=now,
                    data_source="SAMPLE_CSV",
                ))
            elif row["role"] == "DEFICIT":
                deficit.append(DemandNode(
                    kabupaten=kab, commodity=komo,
                    volume_tons=float(row["volume_tons"]),
                    price_per_kg=float(row["price_idr_per_kg"]),
                    timestamp=now,
                    data_source="SAMPLE_CSV",
                ))
            else:
                raise ValueError(f"Unknown role: {row['role']}")
    return surplus, deficit


def load_weather() -> Dict[str, WeatherForecast]:
    """
    Load weather forecast dari weather_forecast.csv.
    Returned dict keyed by '{origin_kab_id}_{dest_kab_id}'
    untuk kompatibilitas dengan engine.run_matching.
    """
    path = os.path.join(SAMPLE_DIR, "weather_forecast.csv")
    out: Dict[str, WeatherForecast] = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = f"{row['origin_kab_id']}_{row['dest_kab_id']}"
            out[key] = WeatherForecast(
                origin_kab_id=row["origin_kab_id"],
                dest_kab_id=row["dest_kab_id"],
                max_rain_mm=float(row["max_rain_mm"]),
                transit_window_days=int(row["transit_window_days"]),
                source=row["source"],
            )
    return out


def load_historical_prices() -> Dict[str, Tuple[float, float]]:
    """
    Load historical price stats dari historical_price_stats.csv.
    Return dict commodity_code → (median, std).
    """
    path = os.path.join(SAMPLE_DIR, "historical_price_stats.csv")
    out: Dict[str, Tuple[float, float]] = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            out[row["commodity_code"]] = (
                float(row["median_idr_per_kg"]),
                float(row["std_idr_per_kg"]),
            )
    return out


def load_all_sample_data(*, surplus_deficit_csv: str = "surplus_deficit.csv"):
    """One-shot loader untuk semua sample data.

    Args:
        surplus_deficit_csv: filename within SAMPLE_DIR for supply/deficit rows.
                             Defaults to canonical "surplus_deficit.csv".
                             Pass "surplus_deficit_constrained.csv" for the
                             La Nina supply-shock scenario fixture.
                             Pass "surplus_deficit_real.csv" for BPS real data.
    """
    kab = load_kabupaten()
    komo = load_komoditas()
    surplus, deficit = load_surplus_deficit(kab, komo, csv_filename=surplus_deficit_csv)
    weather = load_weather()
    historical = load_historical_prices()
    return {
        "kabupaten": kab,
        "komoditas": komo,
        "surplus": surplus,
        "deficit": deficit,
        "weather": weather,
        "historical_prices": historical,
    }


def load_real_data():
    """Load BPS Jawa Timur 2022 real data (6 komoditas: beras_premium, beras_medium,
    cabai_merah, cabai_rawit, bawang_merah, bawang_putih).

    Convenience wrapper around load_all_sample_data(surplus_deficit_csv=...).
    Muat HANYA komoditas yang ada di surplus_deficit_real.csv — tidak ada
    data sintetis di-merge.

    Returns same dict shape as load_all_sample_data().
    """
    return load_all_sample_data(surplus_deficit_csv="surplus_deficit_real.csv")


if __name__ == "__main__":
    print("Testing sample data loader...")
    data = load_all_sample_data()
    print(f"  Kabupaten:    {len(data['kabupaten'])}")
    print(f"  Komoditas:    {len(data['komoditas'])}")
    print(f"  Surplus:      {len(data['surplus'])}")
    print(f"  Deficit:      {len(data['deficit'])}")
    print(f"  Weather:      {len(data['weather'])}")
    print(f"  Historical:   {len(data['historical_prices'])}")
    print("\nSample kabupaten (3 first):")
    for kab_id in list(data["kabupaten"])[:3]:
        k = data["kabupaten"][kab_id]
        print(f"  {kab_id} {k.nama:20s}  IPM={k.ipm}  tier={k.tier.value}")
