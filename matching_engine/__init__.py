"""
AgriFlow Matching Engine
=========================

Public API untuk matching engine 3-lapis.

Quick start:

    from matching_engine import run_matching, SupplyNode, DemandNode, ...

Architecture:
    Layer 0 (constraints.determine_tier)     → Data confidence tier
    Layer 1 (constraints.generate_candidates) → Hard constraint filtering
    Layer 2 (scoring.compute_score)          → 5-dim multi-objective scoring
    Layer 3 (allocation.allocate)            → Stable matching atau Greedy

See engine.run_matching for the main entrypoint.
"""

from .engine import run_matching, is_ramadan_proximity
from .models import (
    Commodity, Confidence, DemandNode, EmergencyMode, Kabupaten,
    LogisticsContext, MatchingReport, MatchResult, ScoreBreakdown,
    SupplyNode, Tier, WeatherForecast,
)
from .constraints import (
    BULOG_PROCUREMENT_KAB, COMMODITY_SPECS, TIER_1_KOTA_IHK,
    determine_tier, generate_candidates, get_commodity, haversine_km,
    is_viable_pair, set_bulog_procurement, reset_bulog_procurement,
)
from .scoring import (
    DEFAULT_WEIGHTS, IMPORT_POLICY_WEIGHTS, RAMADAN_WEIGHTS,
    compute_score, distance_score, volume_score, price_score,
    perishability_score, climate_score,
)
from .allocation import (
    allocate, equity_multiplier_value,
    greedy_match_tier2, stable_match_tier1,
)

__version__ = "9.0.0"

__all__ = [
    # Models
    "Commodity", "Confidence", "DemandNode", "EmergencyMode", "Kabupaten",
    "LogisticsContext", "MatchingReport", "MatchResult", "ScoreBreakdown",
    "SupplyNode", "Tier", "WeatherForecast",
    # Engine
    "run_matching", "is_ramadan_proximity",
    # Constraints
    "BULOG_PROCUREMENT_KAB", "COMMODITY_SPECS", "TIER_1_KOTA_IHK",
    "determine_tier", "generate_candidates", "get_commodity", "haversine_km",
    "is_viable_pair", "set_bulog_procurement", "reset_bulog_procurement",
    # Scoring
    "DEFAULT_WEIGHTS", "IMPORT_POLICY_WEIGHTS", "RAMADAN_WEIGHTS",
    "compute_score", "distance_score", "volume_score", "price_score",
    "perishability_score", "climate_score",
    # Allocation
    "allocate", "equity_multiplier_value",
    "greedy_match_tier2", "stable_match_tier1",
]
