"""
AgriFlow Matching Engine — Layer 2 (Multi-Objective Scoring)
=============================================================

5-dimensi weighted scoring dari Section 5.5.4:
    Distance 22% │ Volume 22% │ Price 22% │ Perishability 18% │ Climate 16%

Setiap komponen dinormalisasi 0-1, lalu di-weight & dikalikan 100.

Author: AgriFlow Team
Version: 9.0
"""

from __future__ import annotations
from typing import Dict, Optional

from .constraints import distance_between, haversine_km
from .models import (
    DemandNode, LogisticsContext, ScoreBreakdown, SupplyNode, WeatherForecast,
)


# =============================================================================
# 1. DISTANCE SCORE — Lebih dekat lebih baik
# =============================================================================

def distance_score(s: SupplyNode, d: DemandNode) -> tuple[float, float]:
    """
    Return (score 0-1, distance_km).
    Linear decay: 0 km → 1.0, MAX_DISTANCE → 0.0.
    """
    dist_km = distance_between(s, d)
    max_viable = s.commodity.max_distance_km
    score = max(0.0, 1.0 - dist_km / max_viable)
    return score, dist_km


# =============================================================================
# 2. VOLUME SCORE — Surplus dan deficit harus seimbang
# =============================================================================

def volume_score(s: SupplyNode, d: DemandNode) -> float:
    """
    Score = matched_volume / larger_volume.
    Perfect 1-to-1 match → 1.0.
    Mismatch besar (10t surplus vs 100t demand) → 0.1.

    Skenario A3 Volume Mismatch Drastis di-flag low score di sini.
    """
    matched = min(s.volume_tons, d.volume_tons)
    larger = max(s.volume_tons, d.volume_tons)
    if larger == 0:
        return 0.0
    return matched / larger


# =============================================================================
# 3. PRICE SCORE — Selisih harga × volume = potensi profit petani
# =============================================================================

def estimate_logistics_cost_per_kg(
    distance_km: float, logistics: LogisticsContext
) -> float:
    """
    Estimasi biaya logistik per kg.
    Formula sederhana: BBM cost / volume per truck + handling fixed.

    Asumsi:
        - Truck colt diesel kapasitas 5 ton
        - Handling fixed Rp 200/kg (bongkar muat + admin)
    """
    bbm_per_km = logistics.bbm_price_idr_per_liter / logistics.truck_consumption_km_per_liter
    bbm_cost_total = bbm_per_km * distance_km
    cost_per_kg_bbm = bbm_cost_total / 5000.0  # 5 ton per truk
    handling_fixed = 200.0  # Rp/kg
    return cost_per_kg_bbm + handling_fixed


def price_score(
    s: SupplyNode,
    d: DemandNode,
    distance_km: float,
    logistics: LogisticsContext,
) -> float:
    """
    Arbitrage = (harga deficit - harga surplus - logistik) / harga surplus.
    Normalize: 0% → 0, ≥50% → 1.0.

    Negative arbitrage (lossy match) → 0.
    Skenario E5 Kenaikan BBM mempengaruhi via logistics.bbm_price.
    """
    if s.price_per_kg <= 0:
        return 0.0
    logistics_cost_per_kg = estimate_logistics_cost_per_kg(distance_km, logistics)
    arbitrage = (d.price_per_kg - s.price_per_kg - logistics_cost_per_kg) / s.price_per_kg
    return min(1.0, max(0.0, arbitrage / 0.50))


# =============================================================================
# 4. PERISHABILITY SCORE — Sisa shelf life harus cukup untuk transit
# =============================================================================

def perishability_score(
    s: SupplyNode,
    d: DemandNode,
    distance_km: float,
    logistics: LogisticsContext,
) -> float:
    """
    Sisa hari segar setelah transit. Margin >5 hari → 1.0, <1 hari → 0.

    Skenario yang relevan:
        - C1 Ramadan Spike → bobot perishability di-up oleh engine
        - D1 Banjir Rute → transit lebih lama → score turun
    """
    transit_days = (
        distance_km / logistics.avg_speed_km_per_hour / logistics.transit_hours_per_day
    )
    remaining = s.commodity.max_fresh_age_days - s.harvest_age_days
    safety_margin = remaining - transit_days
    if safety_margin < 1:
        return 0.0
    return min(1.0, safety_margin / 5.0)


# =============================================================================
# 5. CLIMATE SCORE — Cuaca buruk di rute = penalti
# =============================================================================

def climate_score(
    s: SupplyNode,
    d: DemandNode,
    weather: Optional[WeatherForecast] = None,
) -> float:
    """
    Pakai forecast hujan max di rute selama transit window.

    Tier:
        rain_mm > 50 → 0.3 (hujan deras, transit berisiko)
        rain_mm > 20 → 0.6 (hujan sedang)
        rain_mm <= 20 → 1.0 (cerah/ringan, optimal)

    Default 0.7 jika weather data tidak tersedia (skenario fail-safe).
    Skenario D1 Banjir Rute ditangani di sini.
    """
    if weather is None:
        return 0.7  # neutral fallback
    if weather.max_rain_mm > 50:
        return 0.3
    elif weather.max_rain_mm > 20:
        return 0.6
    else:
        return 1.0


# =============================================================================
# COMPOSITE BASE SCORE
# =============================================================================

# Skema bobot default Section 5.5.4
DEFAULT_WEIGHTS: Dict[str, float] = {
    "distance": 0.22,
    "volume": 0.22,
    "price": 0.22,
    "perishability": 0.18,
    "climate": 0.16,
}

# Skenario C1 Ramadan: bobot perishability & price naik
RAMADAN_WEIGHTS: Dict[str, float] = {
    "distance": 0.20,
    "volume": 0.20,
    "price": 0.20,
    "perishability": 0.22,
    "climate": 0.18,
}

# Skenario E4 Import policy: bobot price turun
IMPORT_POLICY_WEIGHTS: Dict[str, float] = {
    "distance": 0.25,
    "volume": 0.25,
    "price": 0.10,
    "perishability": 0.22,
    "climate": 0.18,
}


def compute_score(
    s: SupplyNode,
    d: DemandNode,
    logistics: Optional[LogisticsContext] = None,
    weather: Optional[WeatherForecast] = None,
    weights: Optional[Dict[str, float]] = None,
) -> tuple[ScoreBreakdown, float, float]:
    """
    Layer 2 main entrypoint.
    Return (breakdown, base_score 0-100, distance_km).
    """
    logistics = logistics or LogisticsContext()
    weights = weights or DEFAULT_WEIGHTS

    # Hitung distance sekali, reuse di score lain
    dist_score, dist_km = distance_score(s, d)
    vol_score = volume_score(s, d)
    pr_score = price_score(s, d, dist_km, logistics)
    perish_score = perishability_score(s, d, dist_km, logistics)
    clim_score = climate_score(s, d, weather)

    breakdown = ScoreBreakdown(
        distance=dist_score,
        volume=vol_score,
        price=pr_score,
        perishability=perish_score,
        climate=clim_score,
    )
    base_score = (
        weights["distance"] * dist_score
        + weights["volume"] * vol_score
        + weights["price"] * pr_score
        + weights["perishability"] * perish_score
        + weights["climate"] * clim_score
    ) * 100
    return breakdown, base_score, dist_km
