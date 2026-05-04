"""
Data Source: PIHPS Bank Indonesia
=================================

Sumber data harga pangan harian untuk 8 kota IHK Jatim (Tier 1).
URL: https://www.bi.go.id/hargapangan/

Mode operasi:
    - real_scrape=True  → scrape live PIHPS website (production)
    - real_scrape=False → baca CSV mock dari sample_data/ (default untuk dev)

Frekuensi update PIHPS: harian (cut-off 13:00 WIB).
Rate limit: tidak ada hard limit publik, tapi tim BI minta < 100 req/menit
            agar tidak overload server.

Output schema:
    {
        "kabupaten_id": str,           # kode BPS, e.g. "3578"
        "kabupaten_nama": str,         # "Kota Surabaya"
        "commodity_code": str,         # "cabai_merah"
        "price_per_kg": float,         # IDR
        "timestamp": datetime,
        "source": "PIHPS"
    }

Author: AgriFlow Team
"""
from __future__ import annotations
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_HTTP_DEPS = True
except ImportError:
    HAS_HTTP_DEPS = False


# 8 kota IHK Jatim (Tier 1) — sumber: BI cakupan PIHPS
TIER1_KOTA_IHK = {
    "3578": "Kota Surabaya",
    "3573": "Kota Malang",
    "3571": "Kota Kediri",
    "3577": "Kota Madiun",
    "3574": "Kota Probolinggo",
    "3510": "Banyuwangi",
    "3529": "Sumenep",
    "3509": "Jember",
}

# Mapping nama komoditas PIHPS → kode internal AgriFlow
PIHPS_COMMODITY_MAP = {
    "Beras Premium": "beras_premium",
    "Beras Medium": "beras_medium",
    "Cabai Merah Besar": "cabai_merah",
    "Cabai Merah Keriting": "cabai_keriting",
    "Cabai Rawit Merah": "cabai_rawit",
    "Bawang Merah": "bawang_merah",
    "Bawang Putih": "bawang_putih",
    "Tomat Sayur": "tomat",
    "Daging Ayam Ras": "daging_ayam",
    "Telur Ayam Ras": "telur_ayam",
    "Minyak Goreng": "minyak_goreng",
    "Gula Pasir": "gula",
    "Daging Sapi": "daging_sapi",
    # ... 19 total di production
}


class PIHPSConnector:
    """
    PIHPS BI connector.

    Usage (mock mode untuk testing):
        conn = PIHPSConnector(real_scrape=False, mock_path="sample_data/pihps_mock.csv")
        prices = conn.fetch_today()

    Usage (production):
        conn = PIHPSConnector(real_scrape=True)
        prices = conn.fetch_today()
    """

    BASE_URL = "https://www.bi.go.id/hargapangan/"

    def __init__(
        self,
        real_scrape: bool = False,
        mock_path: Optional[str] = None,
        timeout: int = 10,
    ):
        self.real_scrape = real_scrape
        self.mock_path = mock_path
        self.timeout = timeout

    def fetch_today(self) -> List[Dict]:
        """
        Fetch harga harian semua komoditas untuk 8 kota IHK.
        Return list of dict (lihat schema di top file).
        """
        if not self.real_scrape:
            return self._fetch_mock()
        if not HAS_HTTP_DEPS:
            raise RuntimeError(
                "requests + beautifulsoup4 dibutuhkan untuk real_scrape mode. "
                "Install: pip install requests beautifulsoup4"
            )
        return self._fetch_real()

    def _fetch_mock(self) -> List[Dict]:
        """Baca data mock dari CSV (untuk development & testing offline)."""
        if not self.mock_path:
            # Default: cari sample_data/surplus_deficit.csv & generate prices
            here = Path(__file__).parent.parent
            self.mock_path = str(here / "sample_data" / "surplus_deficit.csv")

        path = Path(self.mock_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Mock data tidak ditemukan: {path}. "
                f"Generate dulu via `python sample_data/generate_sample_data.py`."
            )

        results: List[Dict] = []
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # surplus_deficit.csv format: kabupaten_id, commodity_code, price_per_kg, ...
                # Hanya untuk Tier 1 IHK (PIHPS official)
                if row.get("kabupaten_id") in TIER1_KOTA_IHK:
                    results.append({
                        "kabupaten_id": row["kabupaten_id"],
                        "kabupaten_nama": TIER1_KOTA_IHK[row["kabupaten_id"]],
                        "commodity_code": row["commodity_code"],
                        "price_per_kg": float(row.get("price_per_kg", 0)),
                        "timestamp": datetime.now(),
                        "source": "PIHPS_MOCK",
                    })
        return results

    def _fetch_real(self) -> List[Dict]:
        """
        Scrape live PIHPS website.
        WARNING: Implementasi ini placeholder — tim perlu adaptasi sesuai
        struktur HTML PIHPS actual saat development. Reverse engineer via
        DevTools Network tab di Chrome → ada AJAX endpoint JSON.

        Pendekatan rekomendasi:
            1. Identifikasi endpoint AJAX (biasanya /hargapangan/api/...)
            2. Pakai endpoint langsung (lebih reliable dari HTML scraping)
            3. Cache 1 jam (PIHPS update sekali sehari)

        Catatan: Per April 2026, BI sudah punya open data API draft.
        Cek https://www.bi.go.id/openapi/ untuk update.
        """
        # PLACEHOLDER — actual implementasi:
        results: List[Dict] = []
        try:
            response = requests.get(
                self.BASE_URL, timeout=self.timeout,
                headers={"User-Agent": "AgriFlow/1.0 (PIDI DIGDAYA Hackathon)"}
            )
            response.raise_for_status()
            # Parse HTML — actual selector tergantung struktur PIHPS
            # Ini contoh skeleton:
            soup = BeautifulSoup(response.text, "html.parser")
            # tables = soup.find_all("table", class_="harga-pangan")
            # ... parse logic ...
            # Untuk hackathon: jika scraping gagal, fallback ke mock
            if not results:
                # Fallback ke mock data
                return self._fetch_mock()
        except requests.RequestException as e:
            print(f"⚠ PIHPS scrape gagal ({e}), fallback ke mock data")
            return self._fetch_mock()
        return results


# =============================================================================
# UTILITY
# =============================================================================

def get_pihps_prices(real_scrape: bool = False) -> List[Dict]:
    """Quick helper untuk fetch PIHPS prices."""
    conn = PIHPSConnector(real_scrape=real_scrape)
    return conn.fetch_today()


if __name__ == "__main__":
    # Smoke test
    print("Testing PIHPS connector (mock mode)...")
    prices = get_pihps_prices(real_scrape=False)
    print(f"Fetched {len(prices)} price entries")
    if prices:
        print("Sample:", prices[0])
