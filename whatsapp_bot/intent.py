"""
Intent classification + slot validation.

Thin layer over GeminiClient that:
    1. Calls Gemini for raw classification
    2. Normalizes slot values (kabupaten name → kab_id, commodity name → code)
    3. Returns a structured Intent object that handlers can consume safely
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .gemini_client import GeminiClient


# =============================================================================
# INTENT TYPES
# =============================================================================

INTENT_HARGA_LOOKUP = "harga_lookup"
INTENT_CARI_PEMBELI = "cari_pembeli"
INTENT_CARI_PENJUAL = "cari_penjual"
INTENT_FALLBACK = "fallback"

VALID_INTENTS = {
    INTENT_HARGA_LOOKUP, INTENT_CARI_PEMBELI,
    INTENT_CARI_PENJUAL, INTENT_FALLBACK,
}


@dataclass
class Intent:
    name: str
    slots: Dict[str, Any] = field(default_factory=dict)
    raw_message: str = ""

    @property
    def commodity(self) -> Optional[str]:
        """Normalized commodity code (e.g. 'cabai_merah') or None."""
        return self.slots.get("commodity")

    @property
    def kabupaten_id(self) -> Optional[str]:
        """Normalized kabupaten id (e.g. '3578') for whichever slot is relevant."""
        return self.slots.get("kabupaten_id")

    @property
    def kabupaten_name(self) -> Optional[str]:
        return self.slots.get("kabupaten_name")

    @property
    def volume_tons(self) -> Optional[float]:
        return self.slots.get("volume_tons")


# =============================================================================
# NORMALIZATION
# =============================================================================

def _normalize_kabupaten(
    raw_name: Optional[str],
    kabupaten_lookup: Dict[str, Any],  # kab_id → Kabupaten
) -> tuple[Optional[str], Optional[str]]:
    """
    Resolve a free-text kabupaten name to (kab_id, canonical_name).
    Tolerates 'Kota Malang' / 'Malang' / 'malang'.
    """
    if not raw_name:
        return None, None
    needle = raw_name.strip().lower()
    # Strip common prefixes
    for prefix in ("kabupaten ", "kab ", "kota "):
        if needle.startswith(prefix):
            needle = needle[len(prefix):]

    # Resolve ambiguity: when the user types "Kediri", both "Kab Kediri" and
    # "Kota Kediri" contain it. Prefer the kabupaten (non-Kota) unless the
    # user explicitly typed "Kota". Fall back to first match if nothing wins.
    user_wants_kota = raw_name.strip().lower().startswith("kota ")
    candidates: list[tuple[str, str, bool]] = []  # (id, nama, is_kota)
    for kab_id, kab in kabupaten_lookup.items():
        kname = kab.nama.lower()
        is_kota = kname.startswith("kota ")
        for prefix in ("kabupaten ", "kab ", "kota "):
            if kname.startswith(prefix):
                kname = kname[len(prefix):]
        if needle == kname or needle in kname or kname in needle:
            candidates.append((kab_id, kab.nama, is_kota))
    if not candidates:
        return None, None
    # Prefer match aligned with user's stated form (Kota vs Kabupaten)
    aligned = [c for c in candidates if c[2] == user_wants_kota]
    chosen = aligned[0] if aligned else candidates[0]
    return chosen[0], chosen[1]


def _normalize_commodity(
    raw_code: Optional[str],
    commodity_lookup: Dict[str, Any],  # code → Commodity
) -> Optional[str]:
    """Validate that LLM-extracted commodity code actually exists."""
    if not raw_code:
        return None
    needle = raw_code.strip().lower()
    if needle in commodity_lookup:
        return needle
    # Fuzzy fallback — match by partial nama
    for code, commodity in commodity_lookup.items():
        if needle in code or needle in commodity.nama.lower():
            return code
    return None


# =============================================================================
# CLASSIFY + NORMALIZE PIPELINE
# =============================================================================

def classify(
    message: str,
    gemini: GeminiClient,
    kabupaten_lookup: Dict[str, Any],
    commodity_lookup: Dict[str, Any],
) -> Intent:
    """End-to-end: raw message → validated Intent with normalized slots."""
    raw = gemini.classify_intent(message)
    name = raw.get("intent", INTENT_FALLBACK)
    if name not in VALID_INTENTS:
        name = INTENT_FALLBACK
    slots = dict(raw.get("slots") or {})

    # Normalize commodity → code
    if "commodity" in slots:
        slots["commodity"] = _normalize_commodity(slots["commodity"], commodity_lookup)

    # Pick whichever kabupaten slot the intent uses + normalize it
    raw_kab = (
        slots.pop("kabupaten", None)
        or slots.pop("kabupaten_origin", None)
        or slots.pop("kabupaten_dest", None)
    )
    kab_id, kab_name = _normalize_kabupaten(raw_kab, kabupaten_lookup)
    slots["kabupaten_id"] = kab_id
    slots["kabupaten_name"] = kab_name

    # Coerce volume to float if present
    if "volume_tons" in slots and slots["volume_tons"] is not None:
        try:
            slots["volume_tons"] = float(slots["volume_tons"])
        except (TypeError, ValueError):
            slots["volume_tons"] = None

    return Intent(name=name, slots=slots, raw_message=message)
