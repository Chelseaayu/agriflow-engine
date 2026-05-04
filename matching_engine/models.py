"""
AgriFlow Matching Engine — Data Models
=======================================

Dataclasses untuk semua entitas yang dipakai matching engine.
Designed agar serializable (untuk API response) dan immutable di mana mungkin.

Author: AgriFlow Team
Version: 9.0
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any


# =============================================================================
# ENUMS
# =============================================================================

class Tier(str, Enum):
    """Confidence tier berdasarkan kualitas data kabupaten."""
    HIGH = "TIER_1_HIGH"        # 8 kota IHK Jatim (PIHPS daily)
    MEDIUM = "TIER_2_MEDIUM"    # 30 kab non-IHK (Bapanas weekly + estimasi)


class Confidence(str, Enum):
    """Confidence label untuk setiap match output."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EmergencyMode(str, Enum):
    """Status emergency/disaster yang aktif untuk satu kabupaten."""
    NORMAL = "NORMAL"
    UNREACHABLE = "UNREACHABLE"     # erupsi, banjir besar
    HUMANITARIAN = "HUMANITARIAN"   # daerah bencana butuh prioritas demand
    PEMDA_LOCKED = "PEMDA_LOCKED"   # do_not_export oleh Pemda


# =============================================================================
# CORE ENTITIES
# =============================================================================

@dataclass
class Kabupaten:
    """Representasi kabupaten/kota Jawa Timur."""
    id: str                         # e.g. "3578" (kode wilayah BPS)
    nama: str                       # e.g. "Surabaya"
    latitude: float
    longitude: float
    ipm: float                      # IPM 2024 BPS
    tier: Tier
    population: int = 0             # untuk konversi konsumsi
    emergency_mode: EmergencyMode = EmergencyMode.NORMAL
    pemda_overrides: Dict[str, bool] = field(default_factory=dict)
    # contoh override: {"do_not_export_cabai_merah": True}

    @property
    def is_tier1(self) -> bool:
        return self.tier == Tier.HIGH

    @property
    def equity_multiplier(self) -> float:
        """
        Equity multiplier berdasarkan IPM (Section 5.5.4 Step 3a).
        Source of truth: matching_engine.allocation.equity_multiplier_value.
        Threshold lihat docstring fungsi tersebut (kalibrasi BPS 2024 Jatim).
        """
        # Lazy import — hindari circular dependency dengan allocation.py.
        from .allocation import equity_multiplier_value
        return equity_multiplier_value(self.ipm)


@dataclass
class Commodity:
    """Spesifikasi komoditas pangan (constraint per komoditas)."""
    code: str                       # e.g. "cabai_merah"
    nama: str                       # e.g. "Cabai Merah Besar"
    max_distance_km: float          # batas jarak transit viable
    min_viable_tons: float          # volume minimum agar match worth it
    max_fresh_age_days: int         # shelf life sejak panen
    bulog_priority: bool = False    # True jika Bulog procurement aktif
    is_imported: bool = False       # True jika ada kebijakan import aktif


@dataclass
class SupplyNode:
    """Surplus dari satu kabupaten untuk satu komoditas pada hari tertentu."""
    kabupaten: Kabupaten
    commodity: Commodity
    volume_tons: float
    price_per_kg: float
    harvest_age_days: int = 0       # 0 = baru panen
    timestamp: datetime = field(default_factory=datetime.now)
    data_source: str = "PIHPS"      # "PIHPS" | "BAPANAS" | "ESTIMATED"

    @property
    def remaining_shelf_days(self) -> int:
        return max(0, self.commodity.max_fresh_age_days - self.harvest_age_days)


@dataclass
class DemandNode:
    """Defisit/kebutuhan dari satu kabupaten untuk satu komoditas."""
    kabupaten: Kabupaten
    commodity: Commodity
    volume_tons: float
    price_per_kg: float
    timestamp: datetime = field(default_factory=datetime.now)
    data_source: str = "PIHPS"


@dataclass
class WeatherForecast:
    """Forecast cuaca pada rute selama transit window."""
    origin_kab_id: str
    dest_kab_id: str
    max_rain_mm: float              # mm hujan maksimum di rute selama transit
    transit_window_days: int = 1
    source: str = "BMKG"            # "BMKG" | "OPEN_METEO"


@dataclass
class LogisticsContext:
    """Variabel logistik global yang mempengaruhi semua match."""
    bbm_price_idr_per_liter: float = 10000.0    # subsidi
    bbm_price_baseline: float = 10000.0         # untuk hitung delta
    truck_consumption_km_per_liter: float = 4.0
    avg_speed_km_per_hour: float = 60.0
    transit_hours_per_day: float = 8.0
    is_ramadan_proximity: bool = False          # H-14 sebelum Idul Fitri
    is_post_harvest_season: bool = False        # Maret-April padi

    @property
    def bbm_change_pct(self) -> float:
        if self.bbm_price_baseline == 0:
            return 0.0
        return (self.bbm_price_idr_per_liter - self.bbm_price_baseline) / self.bbm_price_baseline


# =============================================================================
# OUTPUT TYPES
# =============================================================================

@dataclass
class ScoreBreakdown:
    """Pemecahan 5-dimensi scoring (Section 5.5.4 Layer 2)."""
    distance: float = 0.0           # 0-1
    volume: float = 0.0             # 0-1
    price: float = 0.0              # 0-1
    perishability: float = 0.0      # 0-1
    climate: float = 0.0            # 0-1

    def weighted_total(self) -> float:
        """Bobot Section 5.5.4: 22/22/22/18/16."""
        return (
            0.22 * self.distance
            + 0.22 * self.volume
            + 0.22 * self.price
            + 0.18 * self.perishability
            + 0.16 * self.climate
        ) * 100  # skala 0-100


@dataclass
class MatchResult:
    """Hasil satu pasangan surplus → deficit."""
    surplus: SupplyNode
    deficit: DemandNode
    matched_volume_tons: float
    distance_km: float
    base_score: float                       # 0-100, dari 5-dim weighted
    equity_multiplier: float                # 1.00, 1.05, 1.15, atau 1.30
    final_score: float                      # base_score × equity_multiplier
    confidence: Confidence
    breakdown: ScoreBreakdown
    flags: List[str] = field(default_factory=list)
    # contoh flags: ["RAMADAN_SPIKE", "BULOG_PRIORITY", "EQUITY_BOOST_30"]
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Untuk API response — semua nested object di-flatten."""
        d = asdict(self)
        # convert enum & datetime ke string
        d["confidence"] = self.confidence.value
        d["surplus"]["kabupaten"]["tier"] = self.surplus.kabupaten.tier.value
        d["surplus"]["kabupaten"]["emergency_mode"] = self.surplus.kabupaten.emergency_mode.value
        d["deficit"]["kabupaten"]["tier"] = self.deficit.kabupaten.tier.value
        d["deficit"]["kabupaten"]["emergency_mode"] = self.deficit.kabupaten.emergency_mode.value
        d["surplus"]["timestamp"] = self.surplus.timestamp.isoformat()
        d["deficit"]["timestamp"] = self.deficit.timestamp.isoformat()
        return d


@dataclass
class MatchingReport:
    """Output keseluruhan dari satu run matching engine."""
    matches: List[MatchResult]
    unmatched_surplus: List[SupplyNode] = field(default_factory=list)
    unmatched_deficit: List[DemandNode] = field(default_factory=list)
    external_opportunities: List[str] = field(default_factory=list)
    # contoh: ["Jakarta defisit cabai 800t — suggest ekspor"]
    warnings: List[str] = field(default_factory=list)
    run_metadata: Dict[str, Any] = field(default_factory=dict)
    # contoh: {"latency_ms": 342, "tier1_count": 5, "tier2_count": 13}
