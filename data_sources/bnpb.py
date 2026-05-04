"""
Data Source: BNPB DIBI (Data Informasi Bencana Indonesia)
==========================================================

Untuk skenario D5 (banjir multi-kab) — kabupaten dengan bencana aktif.

URL: https://dibi.bnpb.go.id/
API: https://dibi.bnpb.go.id/dibi3/api/...

Frekuensi update: realtime (saat ada laporan bencana).
Authentication: tidak required untuk read public.

Author: AgriFlow Team
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Dict, List, Set

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# Tipe bencana yang menyebabkan kab unreachable untuk distribusi
DISRUPTIVE_DISASTERS = {
    "BANJIR",       # banjir besar — rute terputus
    "TANAH LONGSOR",
    "GEMPA BUMI",
    "GUNUNG MELETUS",
    "TSUNAMI",
}


class BNPBConnector:
    """
    BNPB DIBI connector untuk fetch bencana aktif Jawa Timur.
    """

    BASE_URL = "https://dibi.bnpb.go.id"
    DEFAULT_TIMEOUT = 15

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout

    def fetch_active_disasters_jatim(
        self,
        days_back: int = 7,
    ) -> List[Dict]:
        """
        Fetch bencana aktif di Jatim dalam N hari terakhir.

        DIBI tidak ada API publik formal — pendekatan production:
            1. Scrape https://dibi.bnpb.go.id/dibi3/peta_bencana
            2. Parse table bencana per provinsi
            3. Filter Jatim (kode 35)

        Untuk hackathon ini, return list manual dari news monitoring + BNPB feed.
        """
        if not HAS_REQUESTS:
            return []

        # Production: scrape DIBI
        # Development/hackathon: return empty atau hardcoded sample
        return []

    def get_affected_kabupaten(self, days_back: int = 7) -> Set[str]:
        """
        Return set kabupaten ID Jatim yang sedang ada bencana disruptif aktif.
        """
        disasters = self.fetch_active_disasters_jatim(days_back=days_back)
        affected: Set[str] = set()
        for d in disasters:
            tipe = d.get("tipe_bencana", "").upper()
            if tipe in DISRUPTIVE_DISASTERS:
                kab_id = d.get("kabupaten_id")
                if kab_id and kab_id.startswith("35"):  # Jatim
                    affected.add(kab_id)
        return affected


def get_disaster_affected_kabupaten(days_back: int = 7) -> Set[str]:
    """Helper: kabupaten dengan bencana aktif."""
    return BNPBConnector().get_affected_kabupaten(days_back=days_back)


if __name__ == "__main__":
    print("Testing BNPB connector...")
    affected = get_disaster_affected_kabupaten()
    print(f"Kabupaten dengan bencana aktif: {affected}")
