"""
Data Source: Badan Pusat Statistik (BPS)
=========================================

Sumber data demografi & produksi tahunan:
    - IPM 2024 per kabupaten (Berita Resmi Statistik Desember 2024)
    - Hortikultura: produksi cabai, bawang, beras per kab
    - Populasi & konsumsi rata-rata

URL: https://webapi.bps.go.id/v1/api/list
Token: required (gratis register di webapi.bps.go.id)

Struktur API (v1):
    GET https://webapi.bps.go.id/v1/api/list/
        domain={kab_id}/lang/ind/key={api_key}/var={var_id}
    Domain: 4-digit kode wilayah BPS, e.g. 3578 = Surabaya
    Lang: ind | eng
    Var:
        - 26: IPM
        - 60: Produksi cabai
        - 61: Produksi bawang merah
        - dst.

Frekuensi update: tahunan (BRS Desember).
Rate limit: 100 req/menit (per akun).

Author: AgriFlow Team
"""
from __future__ import annotations
from typing import Dict, List, Optional
import os

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class BPSConnector:
    """
    BPS WebAPI connector. Token dari env BPS_API_KEY atau argument constructor.

    Usage:
        conn = BPSConnector(api_key="your_token")
        ipm_2024 = conn.fetch_ipm_jatim(year=2024)
    """

    BASE_URL = "https://webapi.bps.go.id/v1/api/list"
    JATIM_KAB_IDS = [
        "3501", "3502", "3503", "3504", "3505", "3506", "3507", "3508",
        "3509", "3510", "3511", "3512", "3513", "3514", "3515", "3516",
        "3517", "3518", "3519", "3520", "3521", "3522", "3523", "3524",
        "3525", "3526", "3527", "3528", "3529",
        "3571", "3572", "3573", "3574", "3575", "3576", "3577", "3578", "3579",
    ]
    # 38 kabupaten/kota Jatim (29 kab + 9 kota)

    VAR_IPM = 26
    VAR_PRODUKSI_CABAI = 60   # tentative — verify dengan BPS docs
    VAR_PRODUKSI_BAWANG = 61

    def __init__(self, api_key: Optional[str] = None, timeout: int = 15):
        self.api_key = api_key or os.getenv("BPS_API_KEY", "")
        self.timeout = timeout

    def _check_key(self):
        if not self.api_key:
            raise ValueError(
                "BPS_API_KEY not set. Register gratis di https://webapi.bps.go.id/, "
                "set env var atau pass api_key= di constructor."
            )

    def fetch_ipm_jatim(self, year: int = 2024) -> Dict[str, float]:
        """
        Fetch IPM untuk semua 38 kab/kota Jatim.
        Return dict: {kab_id: ipm_value}.

        IPM 2024 published Desember 2024 dalam Berita Resmi Statistik.
        """
        if not HAS_REQUESTS:
            raise RuntimeError("requests dibutuhkan.")
        self._check_key()
        results: Dict[str, float] = {}
        for kab_id in self.JATIM_KAB_IDS:
            try:
                url = (
                    f"{self.BASE_URL}/domain/{kab_id}/lang/ind/key/{self.api_key}"
                    f"/var/{self.VAR_IPM}/th/{year}"
                )
                r = requests.get(url, timeout=self.timeout)
                r.raise_for_status()
                data = r.json()
                # Schema: {"status": "OK", "data": [...]}
                if data.get("status") == "OK" and data.get("data"):
                    # Ambil value paling akhir (latest year)
                    val = data["data"][-1].get("value")
                    if val is not None:
                        results[kab_id] = float(val)
            except requests.RequestException as e:
                print(f"⚠ BPS error untuk {kab_id}: {e}")
                continue
        return results

    def fetch_produksi(
        self,
        var_id: int,
        year: int = 2024,
    ) -> Dict[str, float]:
        """
        Fetch produksi komoditas (cabai/bawang/dll) per kab.
        Return dict: {kab_id: tons_produksi_tahunan}.
        """
        if not HAS_REQUESTS:
            raise RuntimeError("requests dibutuhkan.")
        self._check_key()
        results: Dict[str, float] = {}
        for kab_id in self.JATIM_KAB_IDS:
            try:
                url = (
                    f"{self.BASE_URL}/domain/{kab_id}/lang/ind/key/{self.api_key}"
                    f"/var/{var_id}/th/{year}"
                )
                r = requests.get(url, timeout=self.timeout)
                r.raise_for_status()
                data = r.json()
                if data.get("data"):
                    val = data["data"][-1].get("value")
                    if val is not None:
                        results[kab_id] = float(val)
            except requests.RequestException:
                continue
        return results


# =============================================================================
# IPM 2024 BPS HARDCODED (dari BRS Desember 2024)
# =============================================================================
# Sumber: https://jatim.bps.go.id, Berita Resmi Statistik No. XX/XII/35/Th. XXVIII
# Backup data agar engine bisa jalan tanpa BPS API key.

# Source of truth: sample_data/generate_sample_data.py:KABUPATEN_DATA.
# Saat update IPM tahunan, edit di GENERATOR (sample_data) lalu mirror ke sini.
# Lihat sample_data/kabupaten_jatim.csv untuk versi terkompilasi (CSV) yang
# di-load runtime oleh sample_data/loader.py.
IPM_2024_JATIM: Dict[str, float] = {
    "3501": 71.40,  # Pacitan
    "3502": 73.20,  # Ponorogo
    "3503": 73.85,  # Trenggalek
    "3504": 75.30,  # Tulungagung
    "3505": 73.85,  # Blitar (kab)
    "3506": 74.50,  # Kediri (kab)
    "3507": 75.50,  # Malang (kab)
    "3508": 70.10,  # Lumajang
    "3509": 71.86,  # Jember (kab — Tier 1 IHK)
    "3510": 73.45,  # Banyuwangi
    "3511": 69.62,  # Bondowoso
    "3512": 71.20,  # Situbondo
    "3513": 69.40,  # Probolinggo (kab)
    "3514": 71.30,  # Pasuruan (kab)
    "3515": 80.13,  # Sidoarjo
    "3516": 76.50,  # Mojokerto (kab)
    "3517": 75.10,  # Jombang
    "3518": 75.20,  # Nganjuk
    "3519": 71.95,  # Madiun (kab) — wajib boost +15% (range 68-72)
    "3520": 75.80,  # Magetan
    "3521": 74.40,  # Ngawi
    "3522": 73.10,  # Bojonegoro
    "3523": 74.30,  # Tuban
    "3524": 75.60,  # Lamongan
    "3525": 77.61,  # Gresik
    "3526": 67.70,  # Bangkalan          ← +30% boost (range <68)
    "3527": 66.72,  # Sampang ← LOWEST   ← +30% boost (range <68)
    "3528": 70.43,  # Pamekasan
    "3529": 68.79,  # Sumenep (Tier 1 IHK)
    "3571": 81.48,  # Kota Kediri
    "3572": 80.20,  # Kota Blitar
    "3573": 84.05,  # Kota Malang
    "3574": 79.20,  # Kota Probolinggo
    "3575": 79.50,  # Kota Pasuruan
    "3576": 80.85,  # Kota Mojokerto
    "3577": 81.67,  # Kota Madiun
    "3578": 84.69,  # Kota Surabaya ← HIGHEST
    "3579": 78.30,  # Kota Batu
}


def get_ipm_jatim(year: int = 2024, use_api: bool = False) -> Dict[str, float]:
    """
    Get IPM Jatim. Default pakai hardcoded 2024 BPS BRS.
    Set use_api=True untuk fetch live (butuh BPS_API_KEY).
    """
    if use_api:
        try:
            return BPSConnector().fetch_ipm_jatim(year=year)
        except Exception as e:
            print(f"⚠ BPS API gagal ({e}), fallback ke hardcoded IPM 2024.")
    return IPM_2024_JATIM


if __name__ == "__main__":
    ipm = get_ipm_jatim()
    print(f"IPM Jatim 2024: {len(ipm)} kab/kota")
    sorted_ipm = sorted(ipm.items(), key=lambda x: x[1])
    print("3 IPM terendah:")
    for k, v in sorted_ipm[:3]:
        print(f"  {k}: {v}")
    print("3 IPM tertinggi:")
    for k, v in sorted_ipm[-3:]:
        print(f"  {k}: {v}")
