"""
Data Source: PVMBG (Pusat Vulkanologi & Mitigasi Bencana Geologi) MAGMA
=======================================================================

Untuk skenario D4 (erupsi gunung):
    Lumajang → Semeru → status erupsi → emergency_mode=UNREACHABLE

URL: https://magma.esdm.go.id/v1
Endpoint:
    - GET https://magma.esdm.go.id/v1/api/press-release/latest
    - GET https://magma.esdm.go.id/v1/api/aktivitas-gunung-api

Frekuensi update: realtime (saat status berubah).
Rate limit: tidak ada hard limit publik.

Mapping gunung → kabupaten terdampak (curated):
    Semeru → Lumajang, Probolinggo
    Bromo → Probolinggo, Pasuruan, Lumajang, Malang
    Kelud → Kediri, Blitar, Malang
    Ijen → Banyuwangi, Bondowoso
    Arjuno → Pasuruan, Malang
    Welirang → Mojokerto, Pasuruan

Author: AgriFlow Team
"""
from __future__ import annotations
from typing import Dict, List, Optional, Set

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# Status PVMBG levels:
# Normal (1) → Waspada (2) → Siaga (3) → Awas (4)
PVMBG_STATUS_LEVELS = {
    "Normal": 1,
    "Waspada": 2,
    "Siaga": 3,
    "Awas": 4,
}

# Mapping gunung api Jatim → kabupaten terdampak (radius bahaya)
GUNUNG_KABUPATEN_MAP: Dict[str, List[str]] = {
    "Semeru": ["3508", "3513", "3507"],          # Lumajang, Probolinggo, Malang
    "Bromo": ["3513", "3514", "3508", "3507"],   # Probolinggo, Pasuruan, Lumajang, Malang
    "Kelud": ["3506", "3505", "3507"],           # Kediri, Blitar, Malang
    "Ijen": ["3510", "3511"],                    # Banyuwangi, Bondowoso
    "Arjuno-Welirang": ["3514", "3507", "3516"], # Pasuruan, Malang, Mojokerto
    "Raung": ["3510", "3509", "3511"],           # Banyuwangi, Jember, Bondowoso
}


class PVMBGConnector:
    """
    PVMBG MAGMA Indonesia connector.

    Usage:
        conn = PVMBGConnector()
        affected = conn.get_affected_kabupaten(min_status="Siaga")
    """

    BASE_URL = "https://magma.esdm.go.id/v1/api"
    DEFAULT_TIMEOUT = 15

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout

    def fetch_aktivitas(self) -> List[Dict]:
        """
        Fetch aktivitas gunung api terkini.
        Return list of dict: {nama, status, lat, lon, last_update}.
        """
        if not HAS_REQUESTS:
            return []
        try:
            r = requests.get(
                f"{self.BASE_URL}/aktivitas-gunung-api",
                timeout=self.timeout,
                headers={"User-Agent": "AgriFlow/1.0"},
            )
            r.raise_for_status()
            data = r.json()
            return data.get("data", [])
        except requests.RequestException as e:
            print(f"⚠ PVMBG error: {e}")
            return []

    def get_affected_kabupaten(
        self,
        min_status: str = "Siaga",
    ) -> Set[str]:
        """
        Return set kabupaten ID yang terdampak gunung api dengan status
        ≥ min_status. Kabupaten ini harus di-set ke EmergencyMode.UNREACHABLE.
        """
        affected: Set[str] = set()
        target_level = PVMBG_STATUS_LEVELS.get(min_status, 3)

        aktivitas = self.fetch_aktivitas()
        if not aktivitas:
            # Fallback: assume all normal (development mode)
            return affected

        for gunung in aktivitas:
            nama = gunung.get("nama", "")
            status = gunung.get("status", "Normal")
            level = PVMBG_STATUS_LEVELS.get(status, 1)
            if level >= target_level:
                # Cari kabupaten terdampak
                for known_gunung, kab_list in GUNUNG_KABUPATEN_MAP.items():
                    if known_gunung.lower() in nama.lower() or nama.lower() in known_gunung.lower():
                        affected.update(kab_list)

        return affected


def get_unreachable_kabupaten(min_status: str = "Awas") -> Set[str]:
    """Helper: return kab yang harus di-set UNREACHABLE."""
    return PVMBGConnector().get_affected_kabupaten(min_status=min_status)


if __name__ == "__main__":
    print("Testing PVMBG connector...")
    affected = get_unreachable_kabupaten(min_status="Siaga")
    print(f"Kabupaten dengan gunung status ≥ Siaga: {affected}")
