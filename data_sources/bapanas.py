"""
Data Source: Badan Pangan Nasional (Bapanas)
=============================================

Sumber data harga pangan untuk 30 kab non-IHK (Tier 2).
URL: https://panelharga.badanpangan.go.id/

API endpoint (sesuai dokumentasi publik Bapanas):
    GET https://panelharga.badanpangan.go.id/api/front/harga-pangan-table
    Params:
        - province_id: 35 (Jawa Timur)
        - level_harga_id: 3 (harga produsen / pedagang)
        - tanggal: YYYY-MM-DD
        - period_date: "today" | "weekly" | "monthly"

Output Bapanas: harga rata-rata mingguan per kabupaten.
Frekuensi update: mingguan (Senin pagi).
Rate limit: ~60 req/menit (informal).

Note: data Bapanas confidence MEDIUM karena:
    1. Update mingguan (vs PIHPS harian)
    2. Coverage tidak semua kab — gap di-fill dengan estimasi spatial

Author: AgriFlow Team
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Dict, List, Optional

try:
    import requests
    HAS_HTTP_DEPS = True
except ImportError:
    HAS_HTTP_DEPS = False


JATIM_PROVINCE_ID = 35  # kode wilayah BPS


class BapanasConnector:
    """
    Bapanas Panel Harga connector untuk Tier 2 kabupaten.

    Usage:
        conn = BapanasConnector()
        weekly = conn.fetch_weekly(date="2026-04-20")
    """

    API_URL = "https://panelharga.badanpangan.go.id/api/front/harga-pangan-table"
    DEFAULT_TIMEOUT = 15

    def __init__(self, timeout: int = DEFAULT_TIMEOUT, mock_mode: bool = False):
        if not HAS_HTTP_DEPS and not mock_mode:
            raise RuntimeError(
                "requests dibutuhkan. Install: pip install requests"
            )
        self.timeout = timeout
        self.mock_mode = mock_mode

    def fetch_weekly(
        self,
        date: Optional[str] = None,
        commodity_ids: Optional[List[int]] = None,
    ) -> List[Dict]:
        """
        Fetch harga mingguan untuk Jatim.

        Args:
            date: tanggal acuan (default: today)
            commodity_ids: filter per komoditas Bapanas (None = semua)

        Returns:
            List of dict: {kabupaten_id, kabupaten_nama, commodity_code,
                           price_per_kg, week_of, source}

        Raises:
            requests.RequestException jika network error.
        """
        if self.mock_mode:
            return self._mock_response()

        date_str = date or datetime.now().strftime("%Y-%m-%d")
        params = {
            "province_id": JATIM_PROVINCE_ID,
            "level_harga_id": 3,
            "period_date": "weekly",
            "tanggal": date_str,
        }
        if commodity_ids:
            params["commodity_id"] = ",".join(str(c) for c in commodity_ids)

        try:
            response = requests.get(
                self.API_URL,
                params=params,
                timeout=self.timeout,
                headers={"User-Agent": "AgriFlow/1.0"},
            )
            response.raise_for_status()
            data = response.json()
            return self._parse_response(data, week_of=date_str)
        except requests.RequestException as e:
            print(f"⚠ Bapanas API error ({e}). Fallback ke mock.")
            return self._mock_response()

    def _parse_response(self, data: dict, week_of: str) -> List[Dict]:
        """
        Parse Bapanas API response.
        Schema actual harus disesuaikan saat development —
        tim cek response real dulu via:
            curl 'https://panelharga.badanpangan.go.id/api/front/...'
        """
        results: List[Dict] = []
        for entry in data.get("data", []):
            kab_id = str(entry.get("city_id", "")).zfill(4)
            results.append({
                "kabupaten_id": kab_id,
                "kabupaten_nama": entry.get("city_name", ""),
                "commodity_code": self._normalize_commodity(entry.get("commodity_name", "")),
                "price_per_kg": float(entry.get("today", 0)),
                "week_of": week_of,
                "source": "BAPANAS",
            })
        return results

    def _normalize_commodity(self, name: str) -> str:
        """Normalize nama komoditas Bapanas → kode internal AgriFlow."""
        name_lower = name.lower().strip()
        mapping = {
            "beras premium": "beras_premium",
            "beras medium": "beras_medium",
            "cabai merah": "cabai_merah",
            "cabai rawit": "cabai_rawit",
            "bawang merah": "bawang_merah",
            "bawang putih": "bawang_putih",
            "tomat": "tomat",
            "daging ayam": "daging_ayam",
            "telur": "telur_ayam",
            "minyak goreng": "minyak_goreng",
            "gula": "gula",
            "daging sapi": "daging_sapi",
            "kentang": "kentang",
            "wortel": "wortel",
            "kol": "kol",
            "kedelai": "kedelai",
            "jagung": "jagung",
            "ikan": "ikan",
            "udang": "udang",
        }
        for key, code in mapping.items():
            if key in name_lower:
                return code
        return name_lower.replace(" ", "_")

    def _mock_response(self) -> List[Dict]:
        """Mock untuk offline dev — pakai sample_data CSV."""
        from pathlib import Path
        import csv
        path = Path(__file__).parent.parent / "sample_data" / "surplus_deficit.csv"
        if not path.exists():
            return []
        results: List[Dict] = []
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("kabupaten_id", "").startswith("35"):  # Jatim only
                    results.append({
                        "kabupaten_id": row["kabupaten_id"],
                        "kabupaten_nama": row.get("kabupaten_nama", ""),
                        "commodity_code": row["commodity_code"],
                        "price_per_kg": float(row.get("price_per_kg", 0)),
                        "week_of": (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"),
                        "source": "BAPANAS_MOCK",
                    })
        return results


def get_bapanas_weekly(date: Optional[str] = None) -> List[Dict]:
    """Helper helper."""
    return BapanasConnector(mock_mode=True).fetch_weekly(date)


if __name__ == "__main__":
    print("Testing Bapanas connector (mock)...")
    data = get_bapanas_weekly()
    print(f"Fetched {len(data)} entries")
    if data:
        print("Sample:", data[0])
